import bpy
import sys
import os
import tempfile
import numpy as np

sys.path.insert(0, r"d:/1/dlls5 for blender")
import dlss5_blender
dlss5_blender.register()

scene = bpy.context.scene
scene.render.resolution_x = 128
scene.render.resolution_y = 128
scene.render.resolution_percentage = 100

from dlss5_blender.core.image_processor import get_scene_compositor_tree
tree = get_scene_compositor_tree(scene, create=True)
tree.nodes.clear()

rl = tree.nodes.new('CompositorNodeRLayers')
rl.location = (-400, 0)

dlss = tree.nodes.new('CompositorNodeDLSS5')
dlss.location = (-100, 0)

bright = tree.nodes.new('CompositorNodeBrightContrast')
bright.location = (200, 0)
bright.inputs['Bright'].default_value = 0.5

comp = None
for type_name in ('CompositorNodeComposite', 'NodeGroupOutput'):
    try:
        comp = tree.nodes.new(type_name)
        break
    except:
        pass
comp.location = (500, 0)

viewer = tree.nodes.new('CompositorNodeViewer')
viewer.location = (500, -200)

tree.links.new(rl.outputs['Image'], dlss.inputs['Image'])
tree.links.new(dlss.outputs['Image'], bright.inputs['Image'])
tree.links.new(bright.outputs['Image'], comp.inputs['Image'] if 'Image' in comp.inputs else comp.inputs[0])
tree.links.new(bright.outputs['Image'], viewer.inputs['Image'])

print("\n--- Initial Setup Done ---")
print("Tree links:")
for lk in tree.links:
    print(f"  {lk.from_node.name}.{lk.from_socket.name} -> {lk.to_node.name}.{lk.to_socket.name}")

print("\n--- Performing Render 1 ---")
bpy.ops.render.render()

out_img = bpy.data.images.get("DLSS5_Output")
p_out = np.empty(128*128*4, dtype=np.float32)
out_img.pixels.foreach_get(p_out)
print(f"DLSS5_Output min={p_out.min():.4f}, max={p_out.max():.4f}, mean={p_out.mean():.4f}")

temp_exr = os.path.join(tempfile.gettempdir(), f"test_probe_{os.getpid()}.exr")
scene.render.image_settings.file_format = 'OPEN_EXR'
bpy.data.images['Render Result'].save_render(temp_exr, scene=scene)
im_rr = bpy.data.images.load(temp_exr)
p_rr = np.empty(128*128*4, dtype=np.float32)
im_rr.pixels.foreach_get(p_rr)
bpy.data.images.remove(im_rr)
print(f"Render Result (after Render 1) min={p_rr.min():.4f}, max={p_rr.max():.4f}, mean={p_rr.mean():.4f}")

viewer_img = bpy.data.images.get("Viewer Node")
if viewer_img:
    vw, vh = viewer_img.size
    p_v = np.empty(vw*vh*4, dtype=np.float32)
    viewer_img.pixels.foreach_get(p_v)
    print(f"Viewer Node min={p_v.min():.4f}, max={p_v.max():.4f}, mean={p_v.mean():.4f}")

print("\n--- Performing Render 2 ---")
bpy.ops.render.render()

bpy.data.images['Render Result'].save_render(temp_exr, scene=scene)
im_rr = bpy.data.images.load(temp_exr)
im_rr.pixels.foreach_get(p_rr)
bpy.data.images.remove(im_rr)
print(f"Render Result (after Render 2) min={p_rr.min():.4f}, max={p_rr.max():.4f}, mean={p_rr.mean():.4f}")

if viewer_img:
    vw, vh = viewer_img.size
    p_v = np.empty(vw*vh*4, dtype=np.float32)
    viewer_img.pixels.foreach_get(p_v)
    print(f"Viewer Node (after Render 2) min={p_v.min():.4f}, max={p_v.max():.4f}, mean={p_v.mean():.4f}")


print("\nCheck if links were modified:")
for lk in tree.links:
    print(f"  {lk.from_node.name}.{lk.from_socket.name} -> {lk.to_node.name}.{lk.to_socket.name}")
