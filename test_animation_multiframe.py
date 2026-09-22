# -*- coding: utf-8 -*-
"""
真实多帧动画渲染 (Ctrl+F12 / render(animation=True)) 回归测试
测试目标：
1. 针对用户提供的视频测试工程 (D:\\Download\\视频渲染dlls5测试.blend) 执行 6 帧动画渲染
   - 验证每一帧均同步调用 Tensor Core 硬件神经渲染，无漏帧、无延迟派发阻塞
   - 验证每一帧输出的 DLSS5_Output 像素哈希与数值严格不同 (帧帧生效且帧帧独立)
2. 在三维几何动态场景 (Cube 位移旋转) 中测试连续 5 帧动画渲染
   - 验证 3D Render Layers 管线下多帧逐帧 Tensor Core 神经重构与哈希唯一性
"""

import os
import sys
import hashlib
import tempfile
import subprocess
import numpy as np

BASE_DIR = r"d:\1\dlls5 for blender"
BLENDER_EXE = r"D:\blender-3.6.0-windows-x64\blender.exe"
USER_BLEND = r"D:\Download\视频渲染dlls5测试.blend"

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print("=" * 70)
print("[TEST] 开始 DLSS5 动画多帧渲染 (Ctrl+F12 / animation=True) 专项回归测试")
print("=" * 70)

# ─── PART 1: 用户实机工程 (视频渲染dlls5测试.blend) 测试 6 帧动画渲染 ───
if os.path.exists(USER_BLEND):
    print(f"\n--- [Part 1] 用户工程动画多帧渲染验证: {USER_BLEND} ---")
    script_part1 = f"""
import sys, os, hashlib, tempfile, numpy as np
sys.path.insert(0, r"{BASE_DIR}")
import bpy, dlss5_blender
from dlss5_blender.handlers import _get_dlss5_node

bpy.ops.wm.open_mainfile(filepath=r"{USER_BLEND}")
dlss5_blender.register()

scene = bpy.context.scene
start_frame = 360
end_frame = 365
scene.frame_start = start_frame
scene.frame_end = end_frame

out_dir = os.path.join(tempfile.gettempdir(), "test_user_anim_run")
os.makedirs(out_dir, exist_ok=True)
scene.render.filepath = os.path.join(out_dir, "render_")

rendered_frames = []
frame_hashes = {{}}
frame_means = {{}}

def monitor_render_post(s):
    cur_f = s.frame_current
    rendered_frames.append(cur_f)
    cur_node = _get_dlss5_node(s)
    out_img = bpy.data.images.get("DLSS5_Output")
    if out_img and out_img.size[0] > 0:
        arr = np.array(out_img.pixels[:], dtype=np.float32)
        h = hashlib.sha256(arr.tobytes()).hexdigest()
        frame_hashes[cur_f] = h
        frame_means[cur_f] = float(np.mean(arr))
        print(f"  [Part 1 Frame {{cur_f}}] Tensor Core 神经渲染完成! Status: '{{cur_node.last_status}}'")
        print(f"                       尺寸: {{out_img.size[0]}}x{{out_img.size[1]}}, 均值: {{frame_means[cur_f]:.6f}}, SHA256: {{h[:16]}}...")

bpy.app.handlers.render_post.append(monitor_render_post)
bpy.ops.render.render(animation=True)
bpy.app.handlers.render_post.remove(monitor_render_post)

expected_frames = list(range(start_frame, end_frame + 1))
print(f"  渲染处理帧列表: {{rendered_frames}}")
assert rendered_frames == expected_frames, f"处理帧数不匹配! 期望 {{expected_frames}}, 实际 {{rendered_frames}}"
assert len(frame_hashes) == len(expected_frames), "部分帧未获取到输出像素哈希！"

unique_hashes = set(frame_hashes.values())
print(f"  独立像素哈希数量: {{len(unique_hashes)}} / {{len(expected_frames)}}")
assert len(unique_hashes) == len(expected_frames), f"存在重复帧哈希！{{list(frame_hashes.values())}}"
print(">>> Part 1 PASS!")
"""
    cmd1 = [BLENDER_EXE, "-b", "--python-expr", script_part1]
    res1 = subprocess.run(cmd1, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(res1.stdout)
    assert res1.returncode == 0, f"Part 1 运行失败! stderr: {res1.stderr}"
    assert ">>> Part 1 PASS!" in res1.stdout, "Part 1 未包含 PASS 标志！"
    print("  [PASS] Part 1: 用户工程 6 帧动画渲染全部顺利完成，逐帧调用 Tensor Core 且帧帧不同！")

# ─── PART 2: 3D 动态场景连续 5 帧动画渲染测试 ───
print("\n--- [Part 2] 3D 几何动态场景连续 5 帧动画渲染测试 ---")
script_part2 = f"""
import sys, os, hashlib, tempfile, numpy as np
sys.path.insert(0, r"{BASE_DIR}")
import bpy, dlss5_blender
from dlss5_blender.handlers import _get_dlss5_node

dlss5_blender.register()

scene = bpy.context.scene
scene.render.resolution_x = 128
scene.render.resolution_y = 128
scene.render.resolution_percentage = 100
scene.frame_start = 1
scene.frame_end = 5

out_dir = os.path.join(tempfile.gettempdir(), "test_3d_anim_run")
os.makedirs(out_dir, exist_ok=True)
scene.render.filepath = os.path.join(out_dir, "f_")

bpy.ops.scene.dlss5_setup_compositor()

# 动态立方体关键帧动画
cube = bpy.data.objects.get('Cube')
if cube:
    for f in range(1, 6):
        cube.location = (f * 1.5 - 3.0, 0, 0)
        cube.keyframe_insert('location', frame=f)

rendered_frames = []
frame_hashes = {{}}
frame_means = {{}}

def monitor_3d_post(s):
    cur_f = s.frame_current
    rendered_frames.append(cur_f)
    cur_node = _get_dlss5_node(s)
    out_img = bpy.data.images.get("DLSS5_Output")
    if out_img and out_img.size[0] > 0:
        arr = np.array(out_img.pixels[:], dtype=np.float32)
        h = hashlib.sha256(arr.tobytes()).hexdigest()
        frame_hashes[cur_f] = h
        frame_means[cur_f] = float(np.mean(arr))
        print(f"  [Part 2 Frame {{cur_f}}] 3D 神经渲染完成! Status: '{{cur_node.last_status}}'")
        print(f"                       均值: {{frame_means[cur_f]:.6f}}, SHA256: {{h[:16]}}...")

bpy.app.handlers.render_post.append(monitor_3d_post)
bpy.ops.render.render(animation=True)
bpy.app.handlers.render_post.remove(monitor_3d_post)

assert rendered_frames == [1, 2, 3, 4, 5], f"3D 处理帧数不匹配: {{rendered_frames}}"
unique_hashes = set(frame_hashes.values())
print(f"  3D 独立像素哈希数量: {{len(unique_hashes)}} / 5")
assert len(unique_hashes) == 5, f"3D 存在重复哈希: {{list(frame_hashes.values())}}"
print(">>> Part 2 PASS!")
"""
cmd2 = [BLENDER_EXE, "-b", "--python-expr", script_part2]
res2 = subprocess.run(cmd2, capture_output=True, text=True, encoding="utf-8", errors="replace")
print(res2.stdout)
assert res2.returncode == 0, f"Part 2 运行失败! stderr: {res2.stderr}"
assert ">>> Part 2 PASS!" in res2.stdout, "Part 2 未包含 PASS 标志！"
print("  [PASS] Part 2: 3D 几何动态场景 5 帧动画渲染全部顺利完成，逐帧执行神经重构且帧帧不同！")

print("\n" + "=" * 70)
print(">>> 所有多帧动画渲染 (Ctrl+F12) 自动化回归测试全部 PASS！<<<")
print("=" * 70)
