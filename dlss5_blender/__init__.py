# -*- coding: utf-8 -*-
"""
DLSS5 神经渲染 (Neural Rendering) Blender 3.6 原生硬件加速插件
基于 NVIDIA RTX Tensor Core 硬件与 nvngx_dlssnr.dll (Feature ID 18) 的原生图形流水线
"""

bl_info = {
    "name": "DLSS5 神经渲染 (Neural Rendering)",
    "author": "Antigravity & User",
    "version": (3, 0, 0),
    "blender": (3, 6, 0),
    "location": "Compositor > Shift+A > DLSS5 神经渲染, 3D View > N 面板 > DLSS5",
    "description": "基于 NVIDIA RTX 硬件加速与 nvngx_dlssnr.dll 神经网络的 Blender 原生后处理插件",
    "warning": "",
    "doc_url": "",
    "category": "Node",
}

import bpy
from .preferences import DLSS5AddonPreferences, DLSS5_OT_copy_dlls
from .nodes.dlss5_node import CompositorNodeDLSS5, register_node_category, unregister_node_category
from .operators.op_execute import NODE_OT_dlss5_execute, SCENE_OT_dlss5_process_render
from .operators.op_setup_compositor import SCENE_OT_dlss5_setup_compositor
from .ui.panel_view3d import VIEW3D_PT_dlss5_main, VIEW3D_PT_dlss5_compositor
from .handlers import register_handlers, unregister_handlers

classes = [
    DLSS5AddonPreferences,
    DLSS5_OT_copy_dlls,
    CompositorNodeDLSS5,
    NODE_OT_dlss5_execute,
    SCENE_OT_dlss5_process_render,
    SCENE_OT_dlss5_setup_compositor,
    VIEW3D_PT_dlss5_main,
    VIEW3D_PT_dlss5_compositor,
]


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    register_node_category()
    register_handlers()
    print("[DLSS5] v3.0 原生硬件加速插件已加载 (NVIDIA RTX Tensor Core D3D12 Worker)")


def unregister():
    try:
        from .core.dlssnr_bridge import shutdown_engine
        shutdown_engine()
    except Exception:
        pass

    unregister_handlers()
    unregister_node_category()
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
    print("[DLSS5] v3.0 原生硬件加速插件已注销")


if __name__ == "__main__":
    register()
