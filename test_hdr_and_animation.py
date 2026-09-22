import bpy
import sys
import os
import numpy as np

addon_dir = r"d:\1\dlls5 for blender"
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import dlss5_blender
from dlss5_blender.core.dlssnr_bridge import get_engine
from dlss5_blender.core.image_processor import (
    get_or_create_output_image,
    set_numpy_to_image,
    get_image_pixels_as_numpy,
    _set_image_linear_colorspace,
)

print("\n--- [Test HDR] 验证超高动态范围 HDR (数值 > 1.0) 保持与色彩空间 ---")
engine = get_engine()

# Create a test HDR float buffer with values up to 25.0
h, w = 128, 128
hdr_input = np.zeros((h, w, 4), dtype=np.float32)
# Sun/highlight spot with 25.0 intensity
hdr_input[50:70, 50:70, :3] = 25.0
# Midtones
hdr_input[10:30, 10:30, :3] = 0.5
hdr_input[:, :, 3] = 1.0

# Process via Native D3D12
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
}

out_hdr, eng_name = engine.process(hdr_input, params=params)
max_val = out_hdr.max()
print(f"Native D3D12 HDR test: input max={hdr_input.max():.2f}, output max={max_val:.2f}")
assert max_val >= 24.0, f"HDR highlights got clipped! Max was {max_val}"
print("  [PASS] HDR highlights (> 1.0) preserved through D3D12 pipeline!")

# Test writing to image and reading back
img = get_or_create_output_image(w, h, name="HDR_Test_Image")
set_numpy_to_image(img, out_hdr)
read_back = get_image_pixels_as_numpy(img)
assert np.abs(read_back.max() - max_val) < 1e-4, "Image read back max mismatch"
print(f"  [PASS] HDR values successfully stored and read from Blender Image (max={read_back.max():.2f})")
bpy.data.images.remove(img)

print(">>> HDR 验证全部 PASS！")
