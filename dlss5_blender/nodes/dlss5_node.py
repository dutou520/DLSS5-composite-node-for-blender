"""
Blender 合成器自定义后处理节点: CompositorNodeDLSS5
完整支持 DLSS-NR 全部 14 个参数 (与 Magpie 0.6.7 HLSL 对齐)
基于原生 D3D12 Tensor Core 硬件加速执行
"""

import tempfile
import bpy
from bpy.props import (
    FloatProperty, EnumProperty, BoolProperty,
    IntProperty, StringProperty
)

from ..core.image_processor import (
    OUTPUT_IMAGE_NAME,
    get_or_create_output_image,
)

try:
    import nodeitems_utils
    from nodeitems_utils import NodeItem, NodeCategory
    HAS_NODEITEMS = True
except ImportError:
    HAS_NODEITEMS = False

# 优先继承 CompositorNodeCustomGroup，使 Blender C++ 合成引擎将其识别为原生单节点组并顺畅流转像素
CustomGroupBase = getattr(bpy.types, 'CompositorNodeCustomGroup', None)
if CustomGroupBase is None:
    CustomGroupBase = getattr(bpy.types, 'NodeCustomGroup', bpy.types.Node)


class CompositorNodeDLSS5(CustomGroupBase):
    """DLSS5 神经渲染后处理节点 — 原生单节点形态，基于 D3D12 Tensor Core 硬件加速执行"""
    bl_idname = 'CompositorNodeDLSS5'
    bl_label = 'DLSS5 Neural Rendering'
    bl_icon = 'SHADERFX'

    # ─── DLSSNR 核心参数 ───
    style: EnumProperty(
        name="风格模型",
        description="DLSS-NR 神经重构模型风格 (对应 Magpie NR Style)",
        items=[
            ('0', "平衡默认 (Default)", "标准平衡模式，兼顾细节清晰度与画面平滑度"),
            ('1', "自然细腻 (Natural)", "保留原生渲染细节，微对比度柔和自然"),
            ('2', "电影重构 (Cinematic)", "强化光影结构反差与电影级色调层次"),
        ],
        default='0'
    )

    intensity: FloatProperty(
        name="神经渲染强度",
        description="AI 神经渲染重构权重 (NR Intensity: 0=原始, 1=标准, 2=强力)",
        default=1.0, min=0.0, max=2.0, step=5
    )

    local_tone_strength: FloatProperty(
        name="局部色调强度",
        description="微调光照渐变、色调过渡与低频亮度平衡 (Local Tone Strength)",
        default=1.0, min=0.0, max=2.0, step=5
    )

    local_structure_strength: FloatProperty(
        name="局部结构强度",
        description="增强反射、环境光遮蔽、几何微边缘细节 (Local Structure Strength)",
        default=1.0, min=0.0, max=2.0, step=5
    )

    skin_structure_strength: FloatProperty(
        name="微观/皮肤结构",
        description="增强对皮肤、微表面粗糙质感的自适应保护 (Skin Structure Strength)",
        default=0.0, min=0.0, max=2.0, step=5
    )

    # ─── 高级控制 ───
    shadow_structure_multiplier: FloatProperty(
        name="阴影/结构控制",
        description="控制暗部区域的结构细节增强 (Shadow / Structure Control)",
        default=1.0, min=0.0, max=2.0, step=5
    )

    reflection_glow_multiplier: FloatProperty(
        name="反射/辉光控制",
        description="控制亮部反射与辉光效果 (Reflection / Glow Control)",
        default=1.0, min=0.0, max=2.0, step=5
    )

    residual_multiplier: FloatProperty(
        name="残差乘数",
        description="高频细节残差的整体缩放因子 (Residual Multiplier)",
        default=1.0, min=1.0, max=2.0, step=5
    )

    residual_saturation: FloatProperty(
        name="残差饱和度",
        description="残差信号的色彩饱和度调节 (Residual Saturation Multiplier)",
        default=1.0, min=0.0, max=2.0, step=5
    )

    residual_lightness: FloatProperty(
        name="残差亮度",
        description="残差信号的亮度调节 (Residual Lightness Multiplier)",
        default=1.0, min=0.0, max=2.0, step=5
    )

    # ─── 输入分辨率与光流 ───
    enable_input_scaling: BoolProperty(
        name="降低输入分辨率",
        description="将输入缩小后交给 DLSS-NR 处理（降低质量但提高性能）",
        default=False
    )

    input_resolution_percent: IntProperty(
        name="输入分辨率 %",
        description="输入分辨率百分比 (25-100, 仅当启用降分辨率时生效)",
        default=100, min=25, max=100
    )

    optical_flow_method: EnumProperty(
        name="光流方式",
        description="运动矢量计算方式 (Optical Flow Method)",
        items=[
            ('0', "无 (None)", "不使用光流，使用零运动矢量"),
            ('1', "AMD OF", "使用 AMD 光流计算"),
            ('2', "NVIDIA OF", "使用 NVIDIA 光流计算"),
        ],
        default='0'
    )

    # ─── 开关选项 ───
    auto_mask: BoolProperty(
        name="语义 AI 遮罩",
        description="启用基于场景特征的语义自动分离与遮罩 (Automatic Mask)",
        default=False
    )

    ui_correction: BoolProperty(
        name="边缘纠正",
        description="保护高频几何硬轮廓与细线结构 (NR UI Correction)",
        default=True
    )

    auto_process_on_render: BoolProperty(
        name="渲染后自动执行",
        description="渲染完成时自动运行 DLSS5 并刷新输出图像",
        default=True
    )

    # ─── 状态 ───
    last_status: StringProperty(
        name="状态",
        default="就绪"
    )

    last_engine_used: StringProperty(
        name="使用的引擎",
        default=""
    )

    def ensure_internal_tree(self):
        """确保节点具有内部私有节点组树，并在内部封装私有图像输出节点，形成原生单一节点形态"""
        out_img = bpy.data.images.get(OUTPUT_IMAGE_NAME)
        if not out_img:
            out_img = get_or_create_output_image(1920, 1080)

        if self.node_tree is not None:
            # 清理可能导致 Blender 5.x C++ 合成器编译器崩溃的转储节点
            dump_node = self.node_tree.nodes.get("DLSS5_Internal_Dump")
            if dump_node:
                try:
                    self.node_tree.nodes.remove(dump_node)
                except Exception:
                    pass

            img_node = self.node_tree.nodes.get("DLSS5_Internal_Image")
            if not img_node:
                for n in self.node_tree.nodes:
                    if n.bl_idname == 'CompositorNodeImage':
                        img_node = n
                        break
            if img_node and img_node.image != out_img:
                img_node.image = out_img
            return self.node_tree

        tree_name = f"DLSS5_Tree_{self.name}"
        ng = bpy.data.node_groups.new(tree_name, 'CompositorNodeTree')

        # 暴露节点组外部插槽接口 (兼容 Blender 4.0+/5.x 与 Blender 3.x)
        if hasattr(ng, 'interface'):
            ng.interface.new_socket('Image', in_out='INPUT', socket_type='NodeSocketColor')
            ng.interface.new_socket('Depth', in_out='INPUT', socket_type='NodeSocketFloat')
            ng.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
            ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
            ng.interface.new_socket('Alpha', in_out='OUTPUT', socket_type='NodeSocketFloat')
            ng.interface.new_socket('Depth', in_out='OUTPUT', socket_type='NodeSocketFloat')
        else:
            ng.inputs.new('NodeSocketColor', 'Image')
            ng.inputs.new('NodeSocketFloat', 'Depth')
            ng.inputs.new('NodeSocketVector', 'Vector')
            ng.outputs.new('NodeSocketColor', 'Image')
            ng.outputs.new('NodeSocketFloat', 'Alpha')
            ng.outputs.new('NodeSocketFloat', 'Depth')

        ginp = ng.nodes.new('NodeGroupInput')
        ginp.location = (-300, 0)
        gout = ng.nodes.new('NodeGroupOutput')
        gout.location = (300, 0)

        img_node = ng.nodes.new('CompositorNodeImage')
        img_node.name = "DLSS5_Internal_Image"
        img_node.label = "DLSS5 神经重构图像"
        img_node.location = (0, 0)
        img_node.image = out_img

        # 组内连线：图像与 Alpha 直连私有图像节点，深度直通组输入
        if "Image" in img_node.outputs and "Image" in gout.inputs:
            ng.links.new(img_node.outputs["Image"], gout.inputs["Image"])
        if "Alpha" in img_node.outputs and "Alpha" in gout.inputs:
            ng.links.new(img_node.outputs["Alpha"], gout.inputs["Alpha"])
        if "Depth" in ginp.outputs and "Depth" in gout.inputs:
            ng.links.new(ginp.outputs["Depth"], gout.inputs["Depth"])

        self.node_tree = ng
        return self.node_tree

    def init(self, context):
        """初始化节点，构建内部封装管线"""
        self.ensure_internal_tree()

    def copy(self, node):
        """复制节点时独立复制内部节点树"""
        if node.node_tree:
            self.node_tree = node.node_tree.copy()

    def free(self):
        """删除节点时清理内部私有节点树"""
        if self.node_tree:
            try:
                bpy.data.node_groups.remove(self.node_tree)
            except Exception:
                pass

    def draw_buttons(self, context, layout):
        """节点内部控件排版（纯净原生化）"""
        # 风格模型
        layout.prop(self, "style", text="")

        # 核心参数
        col = layout.column(align=True)
        col.prop(self, "intensity", slider=True)
        col.prop(self, "local_tone_strength", slider=True)
        col.prop(self, "local_structure_strength", slider=True)
        col.prop(self, "skin_structure_strength", slider=True)

        # 开关行
        row = layout.row(align=True)
        row.prop(self, "auto_mask", toggle=True)
        row.prop(self, "ui_correction", toggle=True)

        layout.separator(factor=0.3)
        layout.prop(self, "auto_process_on_render")

        # 状态反馈
        if self.last_status or self.last_engine_used:
            box = layout.box()
            if self.last_status:
                icon = 'ERROR' if ('错误' in self.last_status or '失败' in self.last_status) else ('CHECKMARK' if '完成' in self.last_status else 'INFO')
                box.label(text=f"状态: {self.last_status}", icon=icon)
            if self.last_engine_used:
                box.label(text=f"引擎: {self.last_engine_used}", icon='SETTINGS')

    def draw_buttons_ext(self, context, layout):
        """侧边栏 N 面板打开节点时的详细设置（纯净原生化）"""
        # 风格
        box_style = layout.box()
        box_style.label(text="风格与核心参数", icon='SHADING_RENDERED')
        box_style.prop(self, "style")
        col = box_style.column(align=True)
        col.prop(self, "intensity", slider=True)
        col.prop(self, "local_tone_strength", slider=True)
        col.prop(self, "local_structure_strength", slider=True)
        col.prop(self, "skin_structure_strength", slider=True)

        # 高级参数
        box_adv = layout.box()
        box_adv.label(text="高级控制", icon='PREFERENCES')
        col2 = box_adv.column(align=True)
        col2.prop(self, "shadow_structure_multiplier", slider=True)
        col2.prop(self, "reflection_glow_multiplier", slider=True)
        col2.separator(factor=0.5)
        col2.prop(self, "residual_multiplier", slider=True)
        col2.prop(self, "residual_saturation", slider=True)
        col2.prop(self, "residual_lightness", slider=True)

        # 输入与光流
        box_input = layout.box()
        box_input.label(text="输入与光流", icon='MOD_WAVE')
        box_input.prop(self, "enable_input_scaling")
        if self.enable_input_scaling:
            box_input.prop(self, "input_resolution_percent", slider=True)
        box_input.prop(self, "optical_flow_method")

        # 开关
        box_switches = layout.box()
        box_switches.label(text="选项", icon='TOOL_SETTINGS')
        row = box_switches.row(align=True)
        row.prop(self, "auto_mask", toggle=True)
        row.prop(self, "ui_correction", toggle=True)
        box_switches.prop(self, "auto_process_on_render")

        if self.last_status:
            icon = 'ERROR' if ('错误' in self.last_status or '失败' in self.last_status) else ('CHECKMARK' if '完成' in self.last_status else 'INFO')
            layout.label(text=f"状态: {self.last_status}", icon=icon)
        if self.last_engine_used:
            layout.label(text=f"引擎: {self.last_engine_used}", icon='SETTINGS')

    def get_params_dict(self) -> dict:
        """将节点参数导出为字典，供引擎调用"""
        return {
            'style': int(self.style),
            'intensity': self.intensity,
            'local_tone_strength': self.local_tone_strength,
            'local_structure_strength': self.local_structure_strength,
            'skin_structure_strength': self.skin_structure_strength,
            'shadow_structure_multiplier': self.shadow_structure_multiplier,
            'reflection_glow_multiplier': self.reflection_glow_multiplier,
            'residual_multiplier': self.residual_multiplier,
            'residual_saturation': self.residual_saturation,
            'residual_lightness': self.residual_lightness,
            'enable_input_scaling': self.enable_input_scaling,
            'input_resolution_percent': self.input_resolution_percent,
            'optical_flow_method': int(self.optical_flow_method),
            'auto_mask': self.auto_mask,
            'ui_correction': self.ui_correction,
        }


# ─── 合成器 Shift+A 菜单注册 (双轨兼容 Blender 3.6 与 Blender 4.x / 5.x) ───

# 1. 传统 Blender 3.x 注册定义 (基于 nodeitems_utils)
if HAS_NODEITEMS:
    class DLSS5NodeCategory(NodeCategory):
        @classmethod
        def poll(cls, context):
            return getattr(getattr(context, 'space_data', None), 'tree_type', None) == 'CompositorNodeTree'

    node_categories = [
        DLSS5NodeCategory(
            'DLSS5_NODES',
            "DLSS5 神经渲染",
            items=[
                NodeItem("CompositorNodeDLSS5", label="DLSS5 Neural Rendering")
            ]
        )
    ]
else:
    node_categories = []


# 2. 现代 Blender 4.x / 5.x 菜单定义与追加 (基于 NODE_MT_compositor_node_add_all 等)
class NODE_MT_category_dlss5(bpy.types.Menu):
    bl_idname = 'NODE_MT_category_dlss5'
    bl_label = 'DLSS5 神经渲染'

    def draw(self, context):
        layout = self.layout
        props = layout.operator("node.add_node", text="DLSS5 Neural Rendering", icon='SHADERFX')
        props.type = "CompositorNodeDLSS5"
        if hasattr(props, "use_transform"):
            props.use_transform = True


def _menu_draw_compositor_add_all(self, context):
    layout = self.layout
    layout.separator()
    layout.menu('NODE_MT_category_dlss5', text="DLSS5 神经渲染", icon='SHADERFX')


def _menu_draw_compositor_filter(self, context):
    layout = self.layout
    layout.separator()
    props = layout.operator("node.add_node", text="DLSS5 Neural Rendering", icon='SHADERFX')
    props.type = "CompositorNodeDLSS5"
    if hasattr(props, "use_transform"):
        props.use_transform = True


def _menu_draw_node_add(self, context):
    snode = getattr(context, 'space_data', None)
    if snode and getattr(snode, 'tree_type', None) == 'CompositorNodeTree':
        layout = self.layout
        layout.separator()
        layout.menu('NODE_MT_category_dlss5', text="DLSS5 神经渲染", icon='SHADERFX')


def register_node_category():
    # 注册现代 Blender 4/5 菜单类
    try:
        bpy.utils.register_class(NODE_MT_category_dlss5)
    except Exception:
        pass

    # Blender 4.x / 5.x: 注入到 Compositor 的 Shift+A 根菜单、滤镜子菜单及全局添加菜单
    if hasattr(bpy.types, 'NODE_MT_compositor_node_add_all'):
        try:
            bpy.types.NODE_MT_compositor_node_add_all.append(_menu_draw_compositor_add_all)
        except Exception:
            pass

    if hasattr(bpy.types, 'NODE_MT_category_compositor_filter'):
        try:
            bpy.types.NODE_MT_category_compositor_filter.append(_menu_draw_compositor_filter)
        except Exception:
            pass

    if hasattr(bpy.types, 'NODE_MT_add'):
        try:
            bpy.types.NODE_MT_add.append(_menu_draw_node_add)
        except Exception:
            pass

    # Blender 3.x 传统注册
    if HAS_NODEITEMS and node_categories:
        try:
            nodeitems_utils.register_node_categories('DLSS5_NODES', node_categories)
        except Exception:
            pass


def unregister_node_category():
    # Blender 3.x 传统注销
    if HAS_NODEITEMS and node_categories:
        try:
            nodeitems_utils.unregister_node_categories('DLSS5_NODES')
        except Exception:
            pass

    # Blender 4.x / 5.x 菜单注销
    if hasattr(bpy.types, 'NODE_MT_compositor_node_add_all'):
        try:
            bpy.types.NODE_MT_compositor_node_add_all.remove(_menu_draw_compositor_add_all)
        except Exception:
            pass

    if hasattr(bpy.types, 'NODE_MT_category_compositor_filter'):
        try:
            bpy.types.NODE_MT_category_compositor_filter.remove(_menu_draw_compositor_filter)
        except Exception:
            pass

    if hasattr(bpy.types, 'NODE_MT_add'):
        try:
            bpy.types.NODE_MT_add.remove(_menu_draw_node_add)
        except Exception:
            pass

    try:
        bpy.utils.unregister_class(NODE_MT_category_dlss5)
    except Exception:
        pass

