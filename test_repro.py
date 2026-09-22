import bpy
import os
import sys
import numpy as np

# Set up simple scene
scene = bpy.context.scene
scene.render.resolution_x = 320
scene.render.resolution_y = 240
scene.render.resolution_percentage = 100

# Render a frame
bpy.ops.render.render()

# Now inspect Render Result
rr = bpy.data.images.get("Render Result")
print("Render Result found:", rr is not None)

# Add addon directory to sys.path
addon_dir = r"d:/1/dlls5 for blender"
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import dlss5_blender
from dlss5_blender.core.image_processor import get_render_rgba, write_dlss5_output, get_or_create_output_image
from dlss5_blender.core.worker_bridge import get_worker_bridge

rgba = get_render_rgba(scene)
print("RGBA shape:", rgba.shape, "min:", rgba.min(), "max:", rgba.max(), "mean:", rgba.mean())

bridge = get_worker_bridge()
print("Worker ready:", bridge.is_ready, "GPU:", bridge.gpu_name)
out_rgba, eng = bridge.process(rgba, {})
print("out_rgba min:", out_rgba.min(), "max:", out_rgba.max(), "mean:", out_rgba.mean())
print("mean diff:", np.abs(out_rgba - rgba).mean())
