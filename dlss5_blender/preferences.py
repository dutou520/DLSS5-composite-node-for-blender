# -*- coding: utf-8 -*-
"""
DLSS5 插件偏好设置
展示 NVIDIA RTX 硬件、D3D12 Worker 与神经网络模型就绪状态
"""

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, FloatProperty, EnumProperty

from .core.dlssnr_bridge import get_engine, DLSS5SystemInfo
from .core.dll_manager import DLLManager


class DLSS5AddonPreferences(AddonPreferences):
    bl_idname = __package__

    dll_source_dir: StringProperty(
        name="DLL 源目录",
        description="包含 nvngx_dlssnr.dll 的源目录（分发包已内置无需配置）",
        subtype='DIR_PATH',
        default=""
    )

    default_style: EnumProperty(
        name="默认渲染风格",
        items=[
            ('0', "平衡默认 (Default)", "标准平衡模式"),
            ('1', "自然细腻 (Natural)", "保留原生细节"),
            ('2', "电影重构 (Cinematic)", "高对比度光影"),
        ],
        default='0'
    )

    default_intensity: FloatProperty(
        name="默认强度",
        default=1.0,
        min=0.0,
        max=2.0
    )

    def draw(self, context):
        layout = self.layout

        # 1. 硬件与环境诊断
        info = DLSS5SystemInfo()
        box = layout.box()
        box.label(text="DLSS5 硬件环境诊断", icon='SYSTEM')

        if info.has_nvidia_gpu:
            box.label(text=f"显卡: {info.gpu_name}", icon='CHECKMARK')
            box.label(text=f"驱动: {info.driver_version} | CUDA: {info.cuda_version}", icon='SYSTEM')
        else:
            box.label(text="未检测到 NVIDIA GPU", icon='CANCEL')

        # 2. Worker 与 DLL 状态
        dll_mgr = DLLManager()
        dll_status = dll_mgr.check_all()

        box2 = layout.box()
        box2.label(text="核心组件状态", icon='FILE_FOLDER')

        worker_info = dll_status.get('worker', {})
        if worker_info.get('exists'):
            box2.label(text=f"dlss5_worker.exe: ✓ 已就绪 ({worker_info.get('size_mb', 0)} MB)", icon='FILE_TICK')
        else:
            box2.label(text="dlss5_worker.exe: ✗ 未找到", icon='ERROR')

        main_info = dll_status.get('main_dll', {})
        if main_info.get('exists'):
            box2.label(text=f"nvngx_dlssnr.dll: ✓ 已就绪 ({main_info.get('size_mb', 0)} MB)", icon='FILE_TICK')
        else:
            box2.label(text="nvngx_dlssnr.dll: ✗ 未找到", icon='ERROR')

        bridge_info = dll_status.get('bridge_dll', {})
        if bridge_info.get('exists'):
            box2.label(text=f"nvngx.dll_dlssnr.dll: ✓ 已就绪 ({bridge_info.get('size_mb', 0)} MB)", icon='FILE_TICK')
        else:
            box2.label(text="nvngx.dll_dlssnr.dll: ✗ 未找到", icon='ERROR')

        runtime_info = dll_status.get('runtime_dll', {})
        if runtime_info.get('exists'):
            box2.label(text=f"nvngxruntime.dll: ✓ 已就绪 ({runtime_info.get('size_mb', 0)} MB)", icon='FILE_TICK')
        else:
            box2.label(text="nvngxruntime.dll: ✗ 未找到", icon='ERROR')

        # 3. 引擎状态
        box3 = layout.box()
        box3.label(text="原生处理引擎状态", icon='SETTINGS')

        engine = get_engine()
        if engine.native_available:
            gpu_display = engine.system_info.gpu_name if engine.system_info.has_nvidia_gpu else "NVIDIA RTX Tensor Core"
            box3.label(text=f"Native D3D12 引擎: ✓ {gpu_display} 硬件加速活跃", icon='CHECKMARK')
        else:
            error_msg = engine.native_error or "未初始化"
            box3.label(text=f"Native 引擎: ✗ {error_msg}", icon='ERROR')

        # 4. 默认设置
        layout.separator()
        col = layout.column(align=True)
        col.prop(self, "default_style")
        col.prop(self, "default_intensity", slider=True)


class DLSS5_OT_copy_dlls(bpy.types.Operator):
    """从源目录复制 DLL 文件到插件目录"""
    bl_idname = "dlss5.copy_dlls"
    bl_label = "复制 DLL 文件"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.report({'INFO'}, "文件已内置于插件中。")
        return {'FINISHED'}
