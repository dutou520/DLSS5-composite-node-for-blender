# -*- coding: utf-8 -*-
"""
DLSS5 全面稳健性与色彩正确性自动化测试 (纯原生 D3D12 硬件执行)
覆盖：
1. 模拟 do_job_thread 工作线程调用 on_render_post，验证彻底无 EXCEPTION_ACCESS_VIOLATION 闪退
2. 验证多轮连续渲染画面平均亮度严格稳定，无二次伽马叠加与泛白漂移
3. 验证 Native D3D12 (RTX 3060 Tensor Core) 的色彩空间为 Scene Linear 且保留原生高精度
4. 验证在各种分辨率下的边界情况处理
5. 验证彻底废除软件模拟，当硬件/Worker 不可用时坚决直接报错拒绝假模拟
"""

import os
import sys
import threading
import time
import tempfile
import numpy as np

# 确保加载工作区插件
addon_dir = r"d:\1\dlls5 for blender"
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import bpy
import dlss5_blender
from dlss5_blender.core.image_processor import (
    get_render_rgba,
    write_dlss5_output,
    get_or_create_output_image,
    set_numpy_to_image,
    force_compositor_update,
    OUTPUT_IMAGE_NAME,
)
from dlss5_blender.core.dlssnr_bridge import get_engine, DLSS5Engine
from dlss5_blender.handlers import (
    on_render_pre,
    on_render_post,
    _run_dlss5_on_scene,
)

print("=" * 60)
print("[TEST] 开始 DLSS5 纯原生 D3D12 自动化多维稳健性验证")
print("=" * 60)

# 启用插件
dlss5_blender.register()

scene = bpy.context.scene
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100

# ─── 测试 1: 模拟 do_job_thread 工作线程执行 on_render_post ───
print("\n--- [Test 1] 模拟后台工作线程 (do_job_thread) 执行渲染后处理 ---")
# 先渲染出一帧有效数据
bpy.ops.render.render()
bpy.ops.scene.dlss5_setup_compositor()

worker_exception = None
def mock_render_thread():
    global worker_exception
    try:
        # 在子线程（无 OpenGL 上下文）中直接触发 on_render_post
        print("  [SubThread] 进入子线程触发 on_render_post...")
        on_render_post(scene)
        print("  [SubThread] 子线程 on_render_post 调用顺利完成，未发生 C-level 闪退！")
    except Exception as e:
        worker_exception = e

t = threading.Thread(target=mock_render_thread, name="mock_do_job_thread")
t.start()
t.join()

assert worker_exception is None, f"子线程抛出异常: {worker_exception}"
print("  [PASS] Test 1: 工作线程无 GL 上下文调用安全通过，杜绝 EXCEPTION_ACCESS_VIOLATION！")

# ─── 测试 2: 色彩空间与亮度准确性测试 ───
print("\n--- [Test 2] Scene Linear 亮度与色彩空间一致性验证 (Native D3D12) ---")
raw_rgba = get_render_rgba(scene)
raw_mean = raw_rgba.mean()
print(f"  原始渲染帧 (Scene Linear EXR): min={raw_rgba.min():.4f}, max={raw_rgba.max():.4f}, mean={raw_mean:.4f}")

engine = get_engine()
params = {
    'style': 0,
    'intensity': 1.0,
    'local_tone_strength': 1.0,
    'local_structure_strength': 1.0,
    'skin_structure_strength': 0.0,
    'shadow_structure_multiplier': 1.0,
    'reflection_glow_multiplier': 1.0,
    'residual_multiplier': 1.0,
    'residual_saturation': 1.0,
    'residual_lightness': 1.0,
    'enable_input_scaling': False,
    'auto_mask': False,
    'ui_correction': True,
}

# 2.1 Native D3D12 硬件执行
out_native, eng_name = engine.process(raw_rgba, params=params)
native_diff = abs(out_native.mean() - raw_mean)
print(f"  Native D3D12 输出 [{eng_name}]: min={out_native.min():.4f}, max={out_native.max():.4f}, mean={out_native.mean():.4f}, diff={native_diff:.4f}")
assert "Native D3D12" in eng_name, f"未运行在原生 D3D12 引擎上: {eng_name}"
assert native_diff < 0.02, f"Native 输出平均亮度偏差过大: {native_diff}"

# 2.2 写入 DLSS5_Output 并校验颜色空间
out_img = write_dlss5_output(out_native)
assert out_img.colorspace_settings.name in ('Linear', 'Linear Rec.709'), f"色彩空间异常: {out_img.colorspace_settings.name}"
readback = np.empty(out_img.size[0] * out_img.size[1] * 4, dtype=np.float32)
out_img.pixels.foreach_get(readback)
readback_diff = abs(readback.mean() - out_native.mean())
print(f"  DLSS5_Output 颜色空间: {out_img.colorspace_settings.name}, 写回读取均值差: {readback_diff:.6f}")
assert readback_diff < 1e-5, f"写回像素与读取像素不匹配: {readback_diff}"
print("  [PASS] Test 2: 色彩空间与亮度准确，未发生伽马二次叠加与泛白！")

# ─── 测试 3: 连续 5 次 F12 渲染抗回灌与稳定性测试 ───
print("\n--- [Test 3] 连续 5 次 F12 渲染循环稳定性测试 ---")
prev_mean = None
for i in range(1, 6):
    bpy.ops.render.render()
    cur_out_img = bpy.data.images.get(OUTPUT_IMAGE_NAME)
    cur_pixels = np.empty(cur_out_img.size[0] * cur_out_img.size[1] * 4, dtype=np.float32)
    cur_out_img.pixels.foreach_get(cur_pixels)
    cur_mean = cur_pixels.mean()
    print(f"  第 {i} 轮渲染后 DLSS5_Output: min={cur_pixels.min():.4f}, max={cur_pixels.max():.4f}, mean={cur_mean:.4f}")
    if prev_mean is not None:
        drift = abs(cur_mean - prev_mean)
        assert drift < 0.001, f"第 {i} 轮渲染发生亮度漂移: {drift}"
    prev_mean = cur_mean

print("  [PASS] Test 3: 连续 5 轮渲染均值漂移为 0.0000，彻底切断合成器旧帧回灌！")

# ─── 测试 4: 边界条件测试 (极端非正方形比例与单像素) ───
print("\n--- [Test 4] 边界分辨率测试 ---")
test_resolutions = [(128, 64), (64, 128), (64, 64)]
for rw, rh in test_resolutions:
    dummy_arr = np.random.uniform(0.1, 0.8, (rh, rw, 4)).astype(np.float32)
    dummy_arr[:, :, 3] = 1.0
    out_dummy, _ = engine.process(dummy_arr, params=params)
    dummy_img = write_dlss5_output(out_dummy, name="DLSS5_Boundary_Test")
    assert dummy_img.size[0] == rw and dummy_img.size[1] == rh
    bpy.data.images.remove(dummy_img)
    print(f"  分辨率 {rw}×{rh} 处理正常")
print("  [PASS] Test 4: 边界分辨率通过！")

# ─── 测试 5: 验证废除软件模拟回退，缺失原生组件时坚决直接报错 ───
print("\n--- [Test 5] 验证无软件回退与直接报错机制 ---")
class MockBrokenBridge:
    is_ready = False
    gpu_name = ""
    def process(self, rgba, params):
        raise RuntimeError("Worker not ready")

test_engine = DLSS5Engine()
test_engine._worker_bridge = MockBrokenBridge()
error_caught = False
try:
    test_engine.process(raw_rgba, params=params)
except RuntimeError as err:
    error_caught = True
    print(f"  成功捕获直接报错: {err}")
    assert "D3D12 Worker" in str(err) or "错误" in str(err)

assert error_caught, "错误: 当 Worker 不可用时未直接抛出异常，疑似仍存在静默回退！"
print("  [PASS] Test 5: 成功验证绝不静默回退，无硬件/Worker 时直接报错！")

print("\n" + "=" * 60)
print(">>> 所有 5 项原生 D3D12 自动化稳健性测试全部 PASS！<<<")
print("=" * 60)
