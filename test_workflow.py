import bpy
import sys
import os
import numpy as np

# Load addon
addon_dir = r"d:/1/dlls5 for blender"
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import dlss5_blender
dlss5_blender.register()

scene = bpy.context.scene
scene.render.resolution_x = 320
scene.render.resolution_y = 240
scene.render.resolution_percentage = 100

print("\n--- Step 1: Initial Render ---")
bpy.ops.render.render()

# Check initial render layer pixels
import tempfile
temp_exr = os.path.join(tempfile.gettempdir(), "test_step1.exr")
scene.render.image_settings.file_format = 'OPEN_EXR'
bpy.data.images['Render Result'].save_render(temp_exr, scene=scene)
im1 = bpy.data.images.load(temp_exr)
p1 = np.empty(320*240*4, dtype=np.float32)
im1.pixels.foreach_get(p1)
bpy.data.images.remove(im1)
print(f"Step 1 Render Result: min={p1.min():.4f}, max={p1.max():.4f}, mean={p1.mean():.4f}")

print("\n--- Step 2: Setup Compositor ---")
bpy.ops.scene.dlss5_setup_compositor()

# Inspect compositor node connections
from dlss5_blender.core.image_processor import get_scene_compositor_tree
tree = get_scene_compositor_tree(scene)
for lk in tree.links:
    print(f"Link: {lk.from_node.name}.{lk.from_socket.name} -> {lk.to_node.name}.{lk.to_socket.name}")

out_img = bpy.data.images.get("DLSS5_Output")
p_out1 = np.empty(320*240*4, dtype=np.float32)
out_img.pixels.foreach_get(p_out1)
print(f"Step 2 DLSS5_Output: min={p_out1.min():.4f}, max={p_out1.max():.4f}, mean={p_out1.mean():.4f}")

print("\n--- Step 3: Execute DLSS5 ---")
bpy.ops.node.dlss5_execute()

p_out2 = np.empty(320*240*4, dtype=np.float32)
out_img.pixels.foreach_get(p_out2)
print(f"Step 3 DLSS5_Output after execute: min={p_out2.min():.4f}, max={p_out2.max():.4f}, mean={p_out2.mean():.4f}")

print("\n--- Step 4: Render F12 again (with on_render_pre & post) ---")
bpy.ops.render.render()

p_out3 = np.empty(320*240*4, dtype=np.float32)
out_img.pixels.foreach_get(p_out3)
print(f"Step 4 DLSS5_Output after 2nd render: min={p_out3.min():.4f}, max={p_out3.max():.4f}, mean={p_out3.mean():.4f}")

print("\n--- Step 5: Render Result after 2nd render ---")
temp_exr2 = os.path.join(tempfile.gettempdir(), "test_step4.exr")
scene.render.image_settings.file_format = 'OPEN_EXR'
bpy.data.images['Render Result'].save_render(temp_exr2, scene=scene)
im2 = bpy.data.images.load(temp_exr2)
p2 = np.empty(320*240*4, dtype=np.float32)
im2.pixels.foreach_get(p2)
bpy.data.images.remove(im2)
print(f"Step 5 Render Result: min={p2.min():.4f}, max={p2.max():.4f}, mean={p2.mean():.4f}")

print("\n--- Step 6: Render F12 third time ---")
bpy.ops.render.render()
p_out4 = np.empty(320*240*4, dtype=np.float32)
out_img.pixels.foreach_get(p_out4)
print(f"Step 6 DLSS5_Output after 3rd render: min={p_out4.min():.4f}, max={p_out4.max():.4f}, mean={p_out4.mean():.4f}")
