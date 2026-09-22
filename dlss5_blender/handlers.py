# -*- coding: utf-8 -*-
"""
Blender 渲染事件回调处理器
- 渲染完成后自动执行 DLSS5 神经后处理
- 视口合成器实时更新支持（"合成器=总是"模式）
- 1.5 秒 Debounce 防抖机制避免参数拖动时阻塞
"""

import os
import time
import tempfile
import bpy
from bpy.app.handlers import persistent

from .core.dlssnr_bridge import get_engine
from .core.image_processor import (
    get_render_rgba,
    get_active_render_result_image,
    has_render_data,
    write_dlss5_output,
    force_compositor_update,
    get_scene_compositor_tree,
)

# ─── 防抖与缓存状态 ───
_last_process_time = 0.0
_is_processing = False
_DEBOUNCE_SECONDS = 1.5
_last_node_params_hash = None
_last_raw_render_rgba = None  # 视口防抖更新时缓存原始渲染帧，避免参数调节时递归读取合成结果
_last_rendered_frame = None  # 记录最近一次处理的帧号，切帧时强制失效旧缓存
_hijacked_targets = set()  # 保存被 on_render_pre 劫持的 (节点名, 插槽名)


def _get_dlss5_node(scene):
    tree = get_scene_compositor_tree(scene)
    if not tree:
        return None
    for node in tree.nodes:
        if node.bl_idname == 'CompositorNodeDLSS5':
            return node
    return None


def _get_node_params_hash(node) -> int:
    if node is None:
        return 0
    try:
        params = node.get_params_dict()
        return hash(tuple(sorted(
            (k, round(v, 3) if isinstance(v, float) else v)
            for k, v in params.items()
        )))
    except Exception:
        return 0


def _restore_and_link_compositor(tree, node, img_source_node=None, upstream_socket=None):
    """
    [彻底严禁篡改创作者连线]
    保留函数定义以防旧引用报错，实际已完全废除强行重连下游 Composite/Viewer 的逻辑。
    """
    pass


def _run_dlss5_on_scene(scene, node=None, is_viewport_update=False):
    """
    核心处理流程：提取渲染图像 -> DLSS5 C++ D3D12 Worker 处理 -> 写回输出图像数据块 -> 刷新合成器
    彻底严禁篡改创作者的任何节点连线，仅更新内部图像数据块！
    """
    global _is_processing, _last_process_time, _last_node_params_hash
    global _last_raw_render_rgba, _last_rendered_frame

    if _is_processing:
        return False

    _is_processing = True

    tree = get_scene_compositor_tree(scene)
    if node is None and scene:
        node = _get_dlss5_node(scene)

    if node is None:
        _is_processing = False
        return False

    if hasattr(node, 'ensure_internal_tree'):
        node.ensure_internal_tree()

    try:
        rgba = None
        temp_dir = tempfile.gettempdir()
        cur_frame = scene.frame_current if scene else 1

        # 若切帧，强制失效历史渲染帧缓存，保证每一帧严格独立计算
        if _last_rendered_frame is not None and cur_frame != _last_rendered_frame:
            _last_raw_render_rgba = None
        _last_rendered_frame = cur_frame

        # 优先检索当前帧专属转储 OpenEXR 文件
        dump_candidates = [
            os.path.join(temp_dir, f"dlss5_raw_{cur_frame:04d}.exr"),
            os.path.join(temp_dir, f"dlss5_raw_{cur_frame}.exr"),
            os.path.join(temp_dir, f"dlss5_raw_Image{cur_frame:04d}.exr"),
            os.path.join(temp_dir, f"dlss5_raw_Image_{cur_frame:04d}.exr"),
            os.path.join(temp_dir, f"dlss5_raw_Image{cur_frame}.exr"),
            os.path.join(temp_dir, f"dlss5_raw_Image_{cur_frame}.exr"),
        ]

        import glob
        for pat in (f"dlss5_raw_*{cur_frame:04d}*.exr", f"dlss5_raw_*{cur_frame}*.exr"):
            for fpath in glob.glob(os.path.join(temp_dir, pat)):
                if fpath not in dump_candidates:
                    dump_candidates.append(fpath)

        if is_viewport_update:
            dump_candidates.extend([
                os.path.join(temp_dir, "dlss5_raw_Image.exr"),
                os.path.join(temp_dir, "dlss5_raw_.exr"),
            ])

        for candidate in dump_candidates:
            if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                try:
                    loaded = bpy.data.images.load(candidate, check_existing=False)
                    if loaded.size[0] > 0 and loaded.size[1] > 0:
                        from .core.image_processor import get_image_pixels_as_numpy, _set_image_linear_colorspace
                        _set_image_linear_colorspace(loaded)
                        rgba = get_image_pixels_as_numpy(loaded)
                        bpy.data.images.remove(loaded)
                        try:
                            os.remove(candidate)
                        except Exception:
                            pass
                        break
                    else:
                        bpy.data.images.remove(loaded)
                except Exception as e:
                    print(f"[DLSS5] 读取内部缓存 EXR 失败: {e}")

        # 如果上游直接连接了静态/外部 CompositorNodeImage 图像节点
        if rgba is None:
            if "Image" in node.inputs and node.inputs["Image"].is_linked:
                link = node.inputs["Image"].links[0]
                if link.from_node.bl_idname == 'CompositorNodeImage' and link.from_node.image:
                    try:
                        from .core.image_processor import get_image_pixels_as_numpy
                        rgba = get_image_pixels_as_numpy(link.from_node.image)
                    except Exception:
                        pass

        # 仅在纯视口参数防抖微调时复用上一帧缓存；渲染或动画过程中严禁复用以防帧间画面静止
        if is_viewport_update and rgba is None and _last_raw_render_rgba is not None:
            rgba = _last_raw_render_rgba

        # 兜底：从场景 Render Result 提取（适用于 F12 渲染后的情况）
        # 视口拖动时间线时，Render Result 若包含当前帧数据则使用，否则报错退出（不伪造数据）
        if rgba is None:
            try:
                input_image = get_active_render_result_image()
                rgba = get_render_rgba(scene, input_image)
            except Exception as e:
                if not is_viewport_update:
                    print(f"[DLSS5] 获取渲染图像失败: {e}")
                return False


        if rgba is None:
            print("[DLSS5] 未能获取有效输入画面")
            return False

        _last_raw_render_rgba = rgba
        h, w = rgba.shape[:2]

        params = node.get_params_dict()

        engine = get_engine()
        try:
            out_rgba, engine_name = engine.process(
                rgba=rgba,
                params=params,
            )
        except Exception as e:
            err_msg = str(e)
            if node:
                node.last_status = f"{err_msg[:45]}"
                node.last_engine_used = ""
            print(f"[DLSS5 Error] 原生硬件推理异常: {e}")
            return False

        if out_rgba is None:
            if node:
                node.last_status = "错误: 硬件推理失败"
                node.last_engine_used = ""
            return False

        out_img = write_dlss5_output(out_rgba)

        # 确保单节点内部私有图像节点指向重构输出
        if node.node_tree:
            img_node = node.node_tree.nodes.get("DLSS5_Internal_Image")
            if not img_node:
                for n in node.node_tree.nodes:
                    if n.bl_idname == 'CompositorNodeImage':
                        img_node = n
                        break
            if img_node and img_node.image != out_img:
                img_node.image = out_img

        # 兼容旧场景：若外部画布仍有 DLSS5_Image_Output 节点，静默更新图像数据，绝不动连线
        if tree:
            legacy_node = tree.nodes.get("DLSS5_Image_Output")
            if legacy_node and hasattr(legacy_node, "image") and legacy_node.image != out_img:
                legacy_node.image = out_img

        force_compositor_update(scene)

        node.last_status = f"完成 ({w}×{h})"
        node.last_engine_used = engine_name

        _last_process_time = time.time()
        _last_node_params_hash = _get_node_params_hash(node)
        print(f"[DLSS5] 神经渲染完成 [{engine_name}] {w}×{h}")
        return True

    except Exception as e:
        print(f"[DLSS5 Error] 渲染处理异常: {e}")
        return False
    finally:
        _is_processing = False


@persistent
def on_render_init(scene):
    """
    渲染作业启动初始化回调：
    重置所有多帧渲染状态，清除上一帧残留缓存，取消视口更新定时器
    """
    global _is_processing, _last_raw_render_rgba, _last_rendered_frame
    _is_processing = False
    _last_raw_render_rgba = None
    _last_rendered_frame = None

    if bpy.app.timers.is_registered(_do_viewport_update):
        try:
            bpy.app.timers.unregister(_do_viewport_update)
        except Exception:
            pass


@persistent
def on_render_pre(scene):
    """
    每帧渲染开始前回调：
    1. 取消防抖定时器，重置每帧标志位与旧帧缓存
    2. 严格杜绝修改创作者节点树连线
    """
    global _is_processing, _last_raw_render_rgba
    _is_processing = False
    _last_raw_render_rgba = None

    if bpy.app.timers.is_registered(_do_viewport_update):
        try:
            bpy.app.timers.unregister(_do_viewport_update)
        except Exception:
            pass


@persistent
def on_frame_change_pre(scene):
    """
    动画多帧切帧前回调（渲染序列）：
    重置帧间缓存，保证逐帧计算独立，杜绝上一帧画面回灌
    """
    global _is_processing, _last_raw_render_rgba
    _is_processing = False
    _last_raw_render_rgba = None


# ─── 时间线拖动防抖定时器（frame_change_post 专用）───
_TIMELINE_DEBOUNCE_SECONDS = 0.35  # 拖动停止后 350ms 再触发推理，避免逐帧 GPU 推理卡顿
_timeline_last_frame = None        # 最近触发 frame_change_post 的帧号


def _do_timeline_update():
    """
    时间线换帧防抖定时器回调：
    用户停止拖动后延迟执行，从当前帧的合成器中间结果提取图像并推理。
    注意：时间线拖动是视口预览行为，不依赖 auto_process_on_render 渲染自动执行开关；
    只要节点存在且上游 Image 插槽有连线，即响应时间线拖动。
    """
    global _is_processing, _timeline_last_frame

    if _is_processing:
        return None

    # 若当前正在进行正式渲染作业，放弃视口更新，优先保障渲染
    if hasattr(bpy.app, 'is_job_running') and bpy.app.is_job_running('RENDER'):
        return None

    scene = getattr(bpy.context, 'scene', None)
    if scene is None:
        return None

    node = _get_dlss5_node(scene)
    if node is None:
        return None

    # 时间线拖动：只要上游 Image 插槽有任意连线即可触发（不要求 auto_process_on_render）
    # 这样拖动时间线就像其他合成器节点一样实时更新，与渲染后自动执行开关解耦
    has_upstream = "Image" in node.inputs and node.inputs["Image"].is_linked
    if not has_upstream:
        return None

    try:
        success = _run_dlss5_on_scene(scene, node, is_viewport_update=True)
        if success:
            print(f"[DLSS5] 时间线换帧 → 帧 {scene.frame_current} 推理完成")
    except Exception as e:
        print(f"[DLSS5 Timeline] 换帧处理异常: {e}")

    return None


@persistent
def on_frame_change_post(scene):
    """
    时间线换帧后回调（视口拖动时间线专用）：
    防抖注册延迟推理定时器，用户停止拖动后才执行 DLSS5 GPU 推理，
    避免每拖动一帧都立即触发重型推理造成界面卡顿。
    注意：此回调与 _viewport_auto_enabled 解耦，独立于参数防抖更新路径；
    渲染动画序列时也会触发此回调，但彼时 is_job_running('RENDER') 为 True，
    会在 _do_timeline_update 中被拦截，因此不会与 on_render_post 冲突。
    """
    global _last_raw_render_rgba, _timeline_last_frame

    # 若正在正式渲染序列，不干预（由 on_render_post 负责）
    if hasattr(bpy.app, 'is_job_running') and bpy.app.is_job_running('RENDER'):
        return

    node = _get_dlss5_node(scene)
    if node is None:
        return

    # 只要节点存在且上游有连线，就响应时间线拖动（不依赖 _viewport_auto_enabled）
    has_upstream = "Image" in node.inputs and node.inputs["Image"].is_linked
    if not has_upstream:
        return

    cur_frame = scene.frame_current
    _timeline_last_frame = cur_frame

    # 换帧时清除旧帧缓存，确保推理用新帧数据
    _last_raw_render_rgba = None

    # 取消旧定时器，重新注册（防抖：只在最后一帧停顿后触发）
    if bpy.app.timers.is_registered(_do_timeline_update):
        try:
            bpy.app.timers.unregister(_do_timeline_update)
        except Exception:
            pass

    try:
        bpy.app.timers.register(_do_timeline_update, first_interval=_TIMELINE_DEBOUNCE_SECONDS)
    except Exception as e:
        print(f"[DLSS5 Timeline] 注册换帧定时器失败: {e}")



@persistent
def on_render_post(scene):
    """
    单帧或动画序列单帧渲染完成后回调：
    立即同步执行 DLSS5 神经后处理并写回合成器图像数据块。
    无论后台无头模式还是交互式 GUI 模式 (Ctrl+F12 / F12)，
    均在当前帧结束时同步完成，彻底杜绝定时器在动画过程中被抑制导致后续帧不更新的问题。
    """
    target_scene = scene if scene else getattr(bpy.context, 'scene', None)
    node = _get_dlss5_node(target_scene) if target_scene else None
    if node is None or not node.auto_process_on_render:
        return

    try:
        success = _run_dlss5_on_scene(target_scene, node, is_viewport_update=False)
        if not success:
            node.last_status = "自动处理未完成"
    except Exception as e:
        if node:
            node.last_status = f"错误: {str(e)[:40]}"
        print(f"[DLSS5 Error] 渲染后处理异常: {e}")


@persistent
def on_render_complete(scene):
    """渲染作业全部完成回调：重置状态"""
    global _is_processing, _last_raw_render_rgba, _last_rendered_frame
    _is_processing = False
    _last_raw_render_rgba = None
    _last_rendered_frame = None


@persistent
def on_render_cancel(scene):
    """渲染作业取消回调：重置状态"""
    global _is_processing, _last_raw_render_rgba, _last_rendered_frame
    _is_processing = False
    _last_raw_render_rgba = None
    _last_rendered_frame = None


_viewport_auto_enabled = False


def _do_viewport_update():
    """防抖延迟调用的实际处理函数"""
    global _is_processing

    if _is_processing:
        return None

    # 若当前正在进行渲染作业，放弃视口更新，优先保障渲染
    if hasattr(bpy.app, 'is_job_running') and bpy.app.is_job_running('RENDER'):
        return None

    scene = getattr(bpy.context, 'scene', None)
    if scene is None:
        return None

    node = _get_dlss5_node(scene)
    if node is None or not node.auto_process_on_render:
        return None

    # 检查是否有可处理的有效输入
    input_image = None
    if node and "Image" in node.inputs and node.inputs["Image"].is_linked:
        link = node.inputs["Image"].links[0]
        if link.from_node.bl_idname == 'CompositorNodeImage' and link.from_node.image:
            input_image = link.from_node.image

    if input_image is None:
        if not has_render_data(scene):
            return None

    try:
        _run_dlss5_on_scene(scene, node, is_viewport_update=True)
    except Exception as e:
        print(f"[DLSS5 Viewport] 视口更新异常: {e}")

    return None


@persistent
def on_depsgraph_update_post(scene, depsgraph):
    """
    Depsgraph 更新回调：监听 DLSS5 参数变化，执行防抖更新
    """
    global _last_node_params_hash

    if not _viewport_auto_enabled or _is_processing:
        return

    # 若当前正处于渲染中，绝不启动视口更新定时器抢占 GPU/Worker
    if hasattr(bpy.app, 'is_job_running') and bpy.app.is_job_running('RENDER'):
        return

    node = _get_dlss5_node(scene)
    if node is None or not node.auto_process_on_render:
        return

    current_hash = _get_node_params_hash(node)
    if _last_node_params_hash is None:
        _last_node_params_hash = current_hash
        return

    if current_hash == _last_node_params_hash:
        return

    _last_node_params_hash = current_hash

    if bpy.app.timers.is_registered(_do_viewport_update):
        try:
            bpy.app.timers.unregister(_do_viewport_update)
        except Exception:
            pass

    try:
        bpy.app.timers.register(_do_viewport_update, first_interval=_DEBOUNCE_SECONDS)
    except Exception as e:
        print(f"[DLSS5 Viewport] 注册 timer 失败: {e}")


@persistent
def on_load_post(dummy):
    """文件加载完成后，确保所有场景中的 DLSS5 节点内部树与图像数据块就绪"""
    for s in bpy.data.scenes:
        node = _get_dlss5_node(s)
        if node and hasattr(node, 'ensure_internal_tree'):
            try:
                node.ensure_internal_tree()
            except Exception:
                pass


def register_handlers():
    global _viewport_auto_enabled

    if on_render_init not in bpy.app.handlers.render_init:
        bpy.app.handlers.render_init.append(on_render_init)

    if on_render_pre not in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.append(on_render_pre)

    if on_render_post not in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.append(on_render_post)

    if on_frame_change_pre not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(on_frame_change_pre)

    if on_frame_change_post not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(on_frame_change_post)

    if on_render_complete not in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.append(on_render_complete)

    if on_render_cancel not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(on_render_cancel)

    if on_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update_post)

    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)

    _viewport_auto_enabled = True
    print("[DLSS5] 事件处理器已注册（含预渲染保护与多帧动画同步更新、时间线换帧防抖）")



def unregister_handlers():
    global _viewport_auto_enabled

    _viewport_auto_enabled = False

    if bpy.app.timers.is_registered(_do_viewport_update):
        try:
            bpy.app.timers.unregister(_do_viewport_update)
        except Exception:
            pass

    if bpy.app.timers.is_registered(_do_timeline_update):
        try:
            bpy.app.timers.unregister(_do_timeline_update)
        except Exception:
            pass

    if on_render_init in bpy.app.handlers.render_init:
        bpy.app.handlers.render_init.remove(on_render_init)

    if on_render_pre in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(on_render_pre)

    if on_render_post in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.remove(on_render_post)

    if on_frame_change_pre in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(on_frame_change_pre)

    if on_frame_change_post in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(on_frame_change_post)

    if on_render_complete in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(on_render_complete)

    if on_render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(on_render_cancel)

    if on_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update_post)

    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)

    print("[DLSS5] 事件处理器已注销")


