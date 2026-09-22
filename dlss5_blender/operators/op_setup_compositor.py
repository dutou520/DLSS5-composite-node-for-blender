# -*- coding: utf-8 -*-
"""
合成器一键配置操作符
一键建立 DLSS5 节点管线拓扑：
  渲染层 (Render Layers) ──→ DLSS5 自定义参数控制节点
  DLSS5_Image_Output (原生图像节点) ──→ 合成 (Composite) & 预览器 (Viewer)
"""

import bpy
from bpy.types import Operator
from ..core.image_processor import (
    get_active_render_result_image,
    get_or_create_output_image,
    set_numpy_to_image,
    get_image_pixels_as_numpy,
    get_scene_compositor_tree,
)


class SCENE_OT_dlss5_setup_compositor(Operator):
    """一键在合成器中构建 DLSS5 神经渲染节点管线"""
    bl_idname = "scene.dlss5_setup_compositor"
    bl_label = "一键接入合成器 (Setup DLSS5 Pipeline)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        try:
            scene.use_nodes = True
        except Exception:
            pass
        tree = get_scene_compositor_tree(scene, create=True)
        if not tree:
            self.report({'ERROR'}, "无法获取合成器节点树")
            return {'CANCELLED'}
        nodes = tree.nodes
        links = tree.links

        # 1. 获取/创建 渲染层节点
        rl_node = None
        for n in nodes:
            if n.bl_idname == 'CompositorNodeRLayers':
                rl_node = n
                break
        if not rl_node:
            try:
                rl_node = nodes.new('CompositorNodeRLayers')
                rl_node.location = (-500, 200)
            except Exception:
                pass

        # 2. 获取/创建 合成节点 (兼容 3.x/4.x CompositorNodeComposite 与 5.x NodeGroupOutput)
        comp_node = None
        for n in nodes:
            if n.bl_idname in {'CompositorNodeComposite', 'NodeGroupOutput'}:
                comp_node = n
                break
        if not comp_node:
            for type_name in ('CompositorNodeComposite', 'NodeGroupOutput'):
                try:
                    comp_node = nodes.new(type_name)
                    comp_node.location = (700, 200)
                    break
                except Exception:
                    pass

        # 3. 获取/创建 预览器节点
        viewer_node = None
        for n in nodes:
            if n.bl_idname == 'CompositorNodeViewer':
                viewer_node = n
                break
        if not viewer_node:
            try:
                viewer_node = nodes.new('CompositorNodeViewer')
                viewer_node.location = (700, -100)
            except Exception:
                pass

        # 4. 获取/创建 DLSS5 原生单节点组
        dlss_node = None
        for n in nodes:
            if n.bl_idname == 'CompositorNodeDLSS5':
                dlss_node = n
                break
        if not dlss_node:
            dlss_node = nodes.new('CompositorNodeDLSS5')
            dlss_node.location = (100, 200)

        if hasattr(dlss_node, 'ensure_internal_tree'):
            dlss_node.ensure_internal_tree()

        # 清理旧版遗留的额外画布节点 (若存在)
        old_out_node = nodes.get("DLSS5_Image_Output")
        if old_out_node:
            try:
                nodes.remove(old_out_node)
            except Exception:
                pass

        # 初始化输出图像数据块
        w = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
        h = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)
        out_img = get_or_create_output_image(w, h)

        # 5. 原生单节点连线拓扑
        # 渲染层 Image → DLSS5 Image 输入
        if rl_node and "Image" in rl_node.outputs and "Image" in dlss_node.inputs:
            for lk in list(dlss_node.inputs["Image"].links):
                links.remove(lk)
            links.new(rl_node.outputs["Image"], dlss_node.inputs["Image"])

        # 渲染层 Depth → DLSS5 Depth 输入
        if rl_node and "Depth" in rl_node.outputs and "Depth" in dlss_node.inputs:
            for lk in list(dlss_node.inputs["Depth"].links):
                links.remove(lk)
            links.new(rl_node.outputs["Depth"], dlss_node.inputs["Depth"])

        # 渲染层 Vector → DLSS5 Vector 输入 (如果开启了运动矢量 Pass)
        if rl_node and "Vector" in rl_node.outputs and "Vector" in dlss_node.inputs:
            for lk in list(dlss_node.inputs["Vector"].links):
                links.remove(lk)
            links.new(rl_node.outputs["Vector"], dlss_node.inputs["Vector"])

        # DLSS5 节点的 Image 输出直接供给下游（Composite / Viewer）
        dlss_out_sock = dlss_node.outputs.get("Image")
        if dlss_out_sock:
            if comp_node:
                comp_in = comp_node.inputs.get("Image") if "Image" in comp_node.inputs else (comp_node.inputs[0] if comp_node.inputs else None)
                if comp_in:
                    # 若当前直连的是渲染层，替换为直连 DLSS5 单节点
                    for lk in list(comp_in.links):
                        if lk.from_node == rl_node:
                            links.remove(lk)
                    if not comp_in.is_linked:
                        links.new(dlss_out_sock, comp_in)

            if viewer_node and "Image" in viewer_node.inputs:
                for lk in list(viewer_node.inputs["Image"].links):
                    if lk.from_node == rl_node:
                        links.remove(lk)
                if not viewer_node.inputs["Image"].is_linked:
                    links.new(dlss_out_sock, viewer_node.inputs["Image"])

        tree.update_tag()

        self.report(
            {'INFO'},
            "DLSS5 原生单节点管线已就绪！渲染完成后将自动执行神经后处理，无需额外连线。"
        )
        return {'FINISHED'}
