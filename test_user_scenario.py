import bpy
import sys
import os
import tempfile
import numpy as np

sys.path.insert(0, r"d:/1/dlls5 for blender")
import dlss5_blender
dlss5_blender.register()
from dlss5_blender.core.image_processor import get_scene_compositor_tree

scene = bpy.context.scene
scene.render.resolution_x = 320
scene.render.resolution_y = 240
scene.render.resolution_percentage = 100

tree = get_scene_compositor_tree(scene, create=True)
tree.nodes.clear()

rl = tree.nodes.new('CompositorNodeRLayers')
rl.location = (-400, 0)

dlss = tree.nodes.new('CompositorNodeDLSS5')
dlss.location = (-100, 0)

# Downstream grading node: Bright/Contrast with +0.5 Brightness
bright = tree.nodes.new('CompositorNodeBrightContrast')
bright.location = (200, 0)
bright.inputs['Bright'].default_value = 0.5

comp = tree.nodes.new('CompositorNodeComposite')
comp.location = (500, 0)

tree.links.new(rl.outputs['Image'], dlss.inputs['Image'])
tree.links.new(dlss.outputs['Image'], bright.inputs['Image'])
tree.links.new(bright.outputs['Image'], comp.inputs['Image'])

print("\n--- Links before render ---")
for lk in tree.links:
    print(f"  {lk.from_node.name}.{lk.from_socket.name} -> {lk.to_node.name}.{lk.to_socket.name}")

print("\n--- Performing Render 1 ---")
bpy.ops.render.render()

temp_exr = os.path.join(tempfile.gettempdir(), "test_user_render1.exr")
scene.render.image_settings.file_format = 'OPEN_EXR'
bpy.data.images['Render Result'].save_render(temp_exr, scene=scene)
im1 = bpy.data.images.load(temp_exr)
p1 = np.empty(320*240*4, dtype=np.float32)
im1.pixels.foreach_get(p1)
bpy.data.images.remove(im1)
print(f"Render Result 1: min={p1.min():.4f}, max={p1.max():.4f}, mean={p1.mean():.4f}")

out_img = bpy.data.images.get("DLSS5_Output")
p_dlss = np.empty(320*240*4, dtype=np.float32)
out_img.pixels.foreach_get(p_dlss)
print(f"DLSS5_Output after Render 1: min={p_dlss.min():.4f}, max={p_dlss.max():.4f}, mean={p_dlss.mean():.4f}")

print("\n--- Performing Render 2 ---")
bpy.ops.render.render()

bpy.data.images['Render Result'].save_render(temp_exr, scene=scene)
im2 = bpy.data.images.load(temp_exr)
p2 = np.empty(320*240*4, dtype=np.float32)
im2.pixels.foreach_get(p2)
bpy.data.images.remove(im2)
print(f"Render Result 2: min={p2.min():.4f}, max={p2.max():.4f}, mean={p2.mean():.4f}")

out_img.pixels.foreach_get(p_dlss)
print(f"DLSS5_Output after Render 2: min={p_dlss.min():.4f}, max={p_dlss.max():.4f}, mean={p_dlss.mean():.4f}")

print("\n--- Performing Render 3 ---")
bpy.ops.render.render()

bpy.data.images['Render Result'].save_render(temp_exr, scene=scene)
im3 = bpy.data.images.load(temp_exr)
p3 = np.empty(320*240*4, dtype=np.float32)
im3.pixels.foreach_get(p3)
bpy.data.images.remove(im3)
print(f"Render Result 3: min={p3.min():.4f}, max={p3.max():.4f}, mean={p3.mean():.4f}")
