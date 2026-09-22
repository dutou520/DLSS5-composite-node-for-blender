# -*- coding: utf-8 -*-
"""
DLSS5 神经渲染执行操作符
支持 Native D3D12 C++ Worker (RTX 3060 Tensor Core) 硬件加速执行
"""

import time
import bpy
from bpy.types import Operator
from bpy.props import StringProperty

from ..core.dlssnr_bridge import get_engine
from ..core.image_processor import (
    get_render_rgba,
    get_active_render_result_image,
    write_dlss5_output,
    force_compositor_update,
    get_scene_compositor_tree,
)


class NODE_OT_dlss5_execute(Operator):
    """执行当前节点的 DLSS5 神经渲染"""
    bl_idname = "node.dlss5_execute"
    bl_label = "执行 DLSS5 神经渲染"
    bl_options = {'REGISTER', 'UNDO'}

    node_name: StringProperty(name="Node Name", default="")

    def execute(self, context):
        start_time = time.time()
        scene = context.scene

        # 1. 定位 DLSS5 节点
        node = None
        tree = get_scene_compositor_tree(scene)
        if tree:
            if self.node_name:
                node = tree.nodes.get(self.node_name)
            if not node:
                for n in tree.nodes:
                    if n.bl_idname == 'CompositorNodeDLSS5':
                        node = n
                        break

        # 2. 定位输入图像
        input_image = None
        if node and node.inputs["Image"].is_linked:
            link = node.inputs["Image"].links[0]
            from_node = link.from_node
            if from_node.bl_idname == 'CompositorNodeImage' and from_node.image:
                input_image = from_node.image

        if input_image is None:
            input_image = get_active_render_result_image()

        # 3. 提取图像像素
        try:
            rgba = get_render_rgba(scene, input_image)
        except Exception as e:
            self.report({'ERROR'}, f"读取图像失败: {str(e)}")
            if node:
                node.last_status = f"读取失败: {str(e)}"
            return {'CANCELLED'}

        # 4. 构建参数
        if node:
            params = node.get_params_dict()
        else:
            params = {}

        # 5. 获取引擎并执行硬件加速处理
        engine = get_engine()
        h, w = rgba.shape[:2]

        try:
            out_rgba, engine_name = engine.process(
                rgba=rgba,
                params=params,
            )
        except Exception as e:
            err_msg = str(e)
            self.report({'ERROR'}, f"DLSS5 神经渲染失败: {err_msg}")
            if node:
                node.last_status = f"{err_msg[:45]}"
                node.last_engine_used = ""
            return {'CANCELLED'}

        if out_rgba is None:
            err_msg = "错误: 硬件推理失败 (未生成有效画面)"
            self.report({'ERROR'}, err_msg)
            if node:
                node.last_status = err_msg
                node.last_engine_used = ""
            return {'CANCELLED'}

        # 6. 写回输出图像
        out_img = write_dlss5_output(out_rgba)

        # 7. 更新内部私有图像节点 (绝不篡改创作者的任何连线)
        if node and hasattr(node, 'ensure_internal_tree'):
            node.ensure_internal_tree()

        if node and node.node_tree:
            img_node = node.node_tree.nodes.get("DLSS5_Internal_Image")
            if not img_node:
                for n in node.node_tree.nodes:
                    if n.bl_idname == 'CompositorNodeImage':
                        img_node = n
                        break
            if img_node and img_node.image != out_img:
                img_node.image = out_img

        # 兼容旧场景：若外部画布仍有旧版 DLSS5_Image_Output 节点，静默更新图像数据
        if tree:
            legacy_node = tree.nodes.get("DLSS5_Image_Output")
            if legacy_node and hasattr(legacy_node, "image") and legacy_node.image != out_img:
                legacy_node.image = out_img

        # 8. 强制刷新视口与合成器
        force_compositor_update(scene)

        elapsed = round(time.time() - start_time, 3)
        status_str = f"完成 ({w}×{h}, {elapsed}s)"
        if node:
            node.last_status = status_str
            node.last_engine_used = engine_name

        self.report({'INFO'}, f"DLSS5 神经渲染完成 [{engine_name}] 耗时 {elapsed}s")
        return {'FINISHED'}


class SCENE_OT_dlss5_process_render(Operator):
    """自动处理最新渲染结果"""
    bl_idname = "scene.dlss5_process_render"
    bl_label = "DLSS5 神经后处理当前渲染"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.node.dlss5_execute()
        return {'FINISHED'}
