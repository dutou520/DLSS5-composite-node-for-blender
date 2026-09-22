# -*- coding: utf-8 -*-
"""
3D 视口侧边栏 (N 面板) DLSS5 硬件诊断与神经渲染主控制台
"""

import bpy
from bpy.types import Panel
from ..core.dlssnr_bridge import get_engine, DLSS5SystemInfo
from ..core.dll_manager import DLLManager


class VIEW3D_PT_dlss5_base:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "DLSS5"


class VIEW3D_PT_dlss5_main(VIEW3D_PT_dlss5_base, Panel):
    """DLSS5 硬件诊断与引擎状态主面板"""
    bl_idname = "VIEW3D_PT_dlss5_main"
    bl_label = "DLSS5 神经渲染"

    def draw(self, context):
        layout = self.layout

        # 1. GPU 状态诊断
        info = DLSS5SystemInfo()
        box = layout.box()
        if info.has_nvidia_gpu:
            box.label(text=f"GPU: {info.gpu_name}", icon='DISC')
            box.label(text=f"驱动: {info.driver_version} | CUDA: {info.cuda_version}", icon='SYSTEM')
        else:
            box.label(text="未检测到 NVIDIA GPU", icon='ERROR')

        # 2. Worker 与 DLL 状态
        dll_mgr = DLLManager()
        dll_status = dll_mgr.check_all()
        engine = get_engine()

        if dll_status.get('all_present') and engine.native_available:
            gpu_display = info.gpu_name if info.has_nvidia_gpu else "RTX Tensor Core"
            box.label(text=f"状态: {gpu_display} 就绪 ✓", icon='CHECKMARK')
            box.label(text="引擎: D3D12 C++ Worker (Feature ID 18)", icon='SHADERFX')
        else:
            box.label(text=f"状态: {dll_status.get('status_message')}", icon='CANCEL')


class VIEW3D_PT_dlss5_compositor(VIEW3D_PT_dlss5_base, Panel):
    """合成器后处理快捷控制（纯净化原生展示）"""
    bl_idname = "VIEW3D_PT_dlss5_compositor"
    bl_label = "合成器后处理 (Compositor)"
    bl_parent_id = "VIEW3D_PT_dlss5_main"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 查找已有的 DLSS5 节点
        from ..core.image_processor import get_scene_compositor_tree
        dlss_node = None
        tree = get_scene_compositor_tree(scene)
        if tree:
            for n in tree.nodes:
                if n.bl_idname == 'CompositorNodeDLSS5':
                    dlss_node = n
                    break

        if dlss_node:
            box = layout.box()
            box.label(text="节点参数快速调节", icon='PREFERENCES')

            bcol = box.column(align=True)
            bcol.prop(dlss_node, "style")
            bcol.prop(dlss_node, "intensity", slider=True)
            bcol.prop(dlss_node, "local_tone_strength", slider=True)
            bcol.prop(dlss_node, "local_structure_strength", slider=True)
            bcol.prop(dlss_node, "skin_structure_strength", slider=True)

            # 高级参数折叠
            adv_box = box.box()
            adv_box.label(text="高级控制", icon='TOOL_SETTINGS')
            adv_col = adv_box.column(align=True)
            adv_col.prop(dlss_node, "shadow_structure_multiplier", slider=True)
            adv_col.prop(dlss_node, "reflection_glow_multiplier", slider=True)
            adv_col.prop(dlss_node, "residual_multiplier", slider=True)
            adv_col.prop(dlss_node, "residual_saturation", slider=True)
            adv_col.prop(dlss_node, "residual_lightness", slider=True)

            # 开关
            row = box.row(align=True)
            row.prop(dlss_node, "auto_mask", toggle=True)
            row.prop(dlss_node, "ui_correction", toggle=True)

            box.separator(factor=0.3)
            box.prop(dlss_node, "auto_process_on_render")

            # 状态反馈
            if dlss_node.last_status:
                icon = 'ERROR' if ('错误' in dlss_node.last_status or '失败' in dlss_node.last_status) else ('CHECKMARK' if '完成' in dlss_node.last_status else 'INFO')
                box.label(text=f"状态: {dlss_node.last_status}", icon=icon)
            if dlss_node.last_engine_used:
                box.label(text=f"引擎: {dlss_node.last_engine_used}", icon='SETTINGS')
        else:
            box = layout.box()
            box.label(text="在合成器按 Shift+A 添加节点：", icon='INFO')
            box.label(text="「DLSS5 Neural Rendering」", icon='NODETREE')
            box.label(text="连接上游渲染与下游调色即可原生使用")
