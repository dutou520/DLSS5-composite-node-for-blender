# -*- coding: utf-8 -*-
"""
Blender 图像与像素数据交换处理器
- 提取渲染层与合成器输入图像像素为 float32 numpy 数组
- 将 DLSS5 结果写回 Blender Image (GENERATED 类型)
- 刷新视口合成器 (兼容 "合成器: 总是" 模式)
"""

import os
import tempfile
import time
import threading
import bpy
import numpy as np

OUTPUT_IMAGE_NAME = "DLSS5_Output"


def get_scene_compositor_tree(scene, create=False):
    """
    统一获取或创建场景的合成器节点树
    兼容 Blender 3.x/4.x (scene.node_tree) 与 Blender 5.x (scene.compositing_node_group)
    """
    if scene is None:
        return None

    if hasattr(scene, "node_tree"):
        if create and not scene.node_tree:
            try:
                scene.use_nodes = True
            except Exception:
                pass
        return getattr(scene, "node_tree", None)
    elif hasattr(scene, "compositing_node_group"):
        if create and not scene.compositing_node_group:
            try:
                tree = bpy.data.node_groups.new("Compositor", "CompositorNodeTree")
                scene.compositing_node_group = tree
                scene.use_nodes = True
            except Exception:
                pass
        return getattr(scene, "compositing_node_group", None)
    return None


def get_image_pixels_as_numpy(image: bpy.types.Image) -> np.ndarray:
    """
    将 Blender Image 像素提取为 shape=(H, W, 4) 的 float32 numpy 数组
    """
    w, h = image.size
    if w == 0 or h == 0:
        raise ValueError(f"图像 {image.name} 尺寸为 0x0")

    total_floats = w * h * 4
    arr = np.empty(total_floats, dtype=np.float32)
    image.pixels.foreach_get(arr)
    return arr.reshape((h, w, 4))


def set_numpy_to_image(image: bpy.types.Image, rgba_array: np.ndarray):
    """
    将 shape=(H, W, 4) 的 float32 numpy 数组写回到 Blender Image
    并刷新 CPU 与 GPU 纹理缓存
    """
    h, w = rgba_array.shape[:2]
    if image.size[0] != w or image.size[1] != h:
        try:
            if image.source == 'GENERATED':
                image.scale(w, h)
        except Exception:
            pass

    # 务必在写像素前确保色彩空间，避免赋值 colorspace 触发 Blender 重新生成清空已写入的像素
    _set_image_linear_colorspace(image)

    flat = np.ascontiguousarray(rgba_array, dtype=np.float32).ravel()
    image.pixels.foreach_set(flat)
    image.update()
    try:
        image.update_tag()
    except Exception:
        pass

    # 仅在非后台且处于主 UI 线程拥有 OpenGL/GPU 上下文时安全重置纹理缓存
    if not bpy.app.background and threading.current_thread() is threading.main_thread():
        if hasattr(image, 'gl_free'):
            try:
                image.gl_free()
            except Exception:
                pass


def _set_image_linear_colorspace(img: bpy.types.Image):
    """确保图像色彩空间为 Scene Linear (Blender 3.x 为 Linear, 4.x 为 Linear Rec.709)"""
    try:
        current = getattr(img.colorspace_settings, 'name', '')
        available = [item.identifier for item in img.colorspace_settings.bl_rna.properties['name'].enum_items]
        for cs_name in ('Linear', 'Linear Rec.709'):
            if cs_name in available:
                if current != cs_name:
                    img.colorspace_settings.name = cs_name
                break
    except Exception:
        pass


def get_or_create_output_image(width: int, height: int,
                                name: str = OUTPUT_IMAGE_NAME) -> bpy.types.Image:
    """
    获取或创建 DLSS5 输出图像（保持 GENERATED 32-bit Float 格式与 Scene Linear 色彩空间）
    """
    img = bpy.data.images.get(name)
    if img is not None:
        size_ok = (img.size[0] == width and img.size[1] == height)
        is_generated = (img.source == 'GENERATED')
        has_data = getattr(img, 'has_data', True)
        if not size_ok and is_generated:
            try:
                img.scale(width, height)
                size_ok = (img.size[0] == width and img.size[1] == height)
            except Exception:
                pass
        if not size_ok or not is_generated or not has_data:
            try:
                bpy.data.images.remove(img)
            except Exception:
                pass
            img = None

    if img is None:
        img = bpy.data.images.new(
            name=name,
            width=width,
            height=height,
            alpha=True,
            float_buffer=True
        )
        _set_image_linear_colorspace(img)
        try:
            init_buf = np.zeros(width * height * 4, dtype=np.float32)
            init_buf[3::4] = 1.0
            img.pixels.foreach_set(init_buf)
            img.update()
        except Exception:
            pass
    else:
        _set_image_linear_colorspace(img)

    return img


def get_active_render_result_image() -> bpy.types.Image:
    """查找可用的渲染输出图像 (Render Result)"""
    return bpy.data.images.get("Render Result")


def has_render_data(scene: bpy.types.Scene) -> bool:
    """检查场景当前是否已有完成的渲染帧数据"""
    rr = bpy.data.images.get("Render Result")
    if rr is None:
        return False
    probe_path = os.path.join(tempfile.gettempdir(), f"dlss5_probe_{os.getpid()}_{time.time_ns()}.exr")
    orig_fmt = scene.render.image_settings.file_format
    try:
        scene.render.image_settings.file_format = 'OPEN_EXR'
        rr.save_render(probe_path, scene=scene)
        if os.path.exists(probe_path):
            try:
                os.remove(probe_path)
            except Exception:
                pass
            return True
    except Exception:
        pass
    finally:
        scene.render.image_settings.file_format = orig_fmt
    return False


def get_render_rgba(scene: bpy.types.Scene,
                    input_image: bpy.types.Image = None) -> np.ndarray:
    """
    从 Blender 获取渲染帧的 RGBA float32 数组 (严格保持 32-bit 浮点与 Scene Linear 线性色彩空间)
    """
    # 1. 如果显式指定了有效的外部/生成图像 (非 Render Result 且非 DLSS5_Output)
    if (input_image
            and input_image.name not in {"Render Result", OUTPUT_IMAGE_NAME}
            and input_image.size[0] > 0
            and input_image.size[1] > 0):
        return get_image_pixels_as_numpy(input_image)

    # 2. 从 Render Result 提取真实渲染帧 (严格保存为 32-bit 未压缩 OpenEXR，彻底避免 PNG/sRGB 伽马污染)
    rr = bpy.data.images.get("Render Result")
    if rr is not None:
        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"dlss5_raw_{os.getpid()}_{time.time_ns()}.exr"
        )

        orig_fmt = scene.render.image_settings.file_format
        orig_depth = scene.render.image_settings.color_depth
        orig_mode = scene.render.image_settings.color_mode
        orig_exr_codec = getattr(scene.render.image_settings, 'exr_codec', 'ZIP')
        orig_cm = getattr(scene.render.image_settings, 'color_management', None)

        try:
            scene.render.image_settings.file_format = 'OPEN_EXR'
            scene.render.image_settings.color_depth = '32'
            scene.render.image_settings.color_mode = 'RGBA'
            if hasattr(scene.render.image_settings, 'exr_codec'):
                scene.render.image_settings.exr_codec = 'NONE'
            if hasattr(scene.render.image_settings, 'color_management'):
                scene.render.image_settings.color_management = 'FOLLOW_SCENE'
            rr.save_render(temp_path, scene=scene)
        except Exception as e:
            print(f"[DLSS5 Error] 无法导出渲染帧 OpenEXR: {e}")
        finally:
            scene.render.image_settings.file_format = orig_fmt
            scene.render.image_settings.color_depth = orig_depth
            scene.render.image_settings.color_mode = orig_mode
            if hasattr(scene.render.image_settings, 'exr_codec'):
                scene.render.image_settings.exr_codec = orig_exr_codec
            if orig_cm is not None and hasattr(scene.render.image_settings, 'color_management'):
                scene.render.image_settings.color_management = orig_cm

        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            try:
                loaded = bpy.data.images.load(temp_path, check_existing=False)
                _set_image_linear_colorspace(loaded)
                rgba = get_image_pixels_as_numpy(loaded)
                bpy.data.images.remove(loaded)
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
                return rgba
            except Exception as e:
                print(f"[DLSS5 Warning] 读取渲染 EXR 文件失败: {e}")
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    # 3. 最终回退：根据当前场景分辨率构造纯色测试缓冲区
    w = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    h = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)
    fallback = np.zeros((h, w, 4), dtype=np.float32)
    fallback[:, :, 3] = 1.0
    return fallback


def write_dlss5_output(out_rgba: np.ndarray,
                       name: str = OUTPUT_IMAGE_NAME) -> bpy.types.Image:
    """
    写回输出图像并刷新 GPU 纹理
    """
    h, w = out_rgba.shape[:2]
    out_img = get_or_create_output_image(w, h, name)
    set_numpy_to_image(out_img, out_rgba)
    return out_img


def force_compositor_update(scene=None):
    """强制刷新 Blender 合成器与 3D 视口渲染"""
    if scene is None:
        scene = getattr(bpy.context, 'scene', None)

    try:
        tree = get_scene_compositor_tree(scene)
        if tree:
            tree.update_tag()
            for n in tree.nodes:
                if n.bl_idname == 'CompositorNodeImage' and n.image and n.image.name == OUTPUT_IMAGE_NAME:
                    if hasattr(n, 'update_tag'):
                        try:
                            n.update_tag()
                        except Exception:
                            pass
                elif n.bl_idname == 'CompositorNodeDLSS5':
                    if hasattr(n, 'update_tag'):
                        try:
                            n.update_tag()
                        except Exception:
                            pass
                    if getattr(n, 'node_tree', None):
                        try:
                            n.node_tree.update_tag()
                            for sub_n in n.node_tree.nodes:
                                if hasattr(sub_n, 'update_tag'):
                                    try:
                                        sub_n.update_tag()
                                    except Exception:
                                        pass
                        except Exception:
                            pass
    except Exception:
        pass

    out_img = bpy.data.images.get(OUTPUT_IMAGE_NAME)
    if out_img:
        try:
            out_img.update()
            out_img.update_tag()
        except Exception:
            pass

    try:
        wm = getattr(bpy.context, 'window_manager', None)
        if wm and hasattr(wm, 'windows'):
            for window in wm.windows:
                for area in window.screen.areas:
                    if area.type in {'NODE_EDITOR', 'VIEW_3D', 'IMAGE_EDITOR'}:
                        area.tag_redraw()
    except Exception:
        pass
