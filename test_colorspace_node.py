import bpy
import numpy as np
import tempfile
import os

# Create simple test scene
scene = bpy.context.scene
scene.render.resolution_x = 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.use_nodes = True

tree = scene.node_tree
tree.nodes.clear()

rl = tree.nodes.new('CompositorNodeRLayers')
comp = tree.nodes.new('CompositorNodeComposite')
tree.links.new(rl.outputs['Image'], comp.inputs['Image'])

# Render baseline
bpy.ops.render.render()
rr = bpy.data.images['Render Result']
base_path = os.path.join(tempfile.gettempdir(), 'base.exr')
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '32'
rr.save_render(base_path, scene=scene)

base_img = bpy.data.images.load(base_path)
base_pixels = np.empty(64*64*4, dtype=np.float32)
base_img.pixels.foreach_get(base_pixels)
bpy.data.images.remove(base_img)

print("Baseline Render Layers -> Composite:")
print("  min:", base_pixels.min(), "max:", base_pixels.max(), "mean:", base_pixels.mean())

# Now test: pass base_pixels into an Image datablock, hook up to CompositorNodeImage -> Composite, and render again!
for cs_name in ['Linear', 'sRGB', 'Non-Color']:
    test_img = bpy.data.images.new(f"Test_{cs_name}", width=64, height=64, alpha=True, float_buffer=True)
    try:
        test_img.colorspace_settings.name = cs_name
    except Exception as e:
        print(f"Cannot set colorspace {cs_name}: {e}")
    test_img.pixels.foreach_set(base_pixels)
    test_img.update()

    # Now hook test_img into Compositor
    tree.links.clear()
    img_node = tree.nodes.new('CompositorNodeImage')
    img_node.image = test_img
    tree.links.new(img_node.outputs['Image'], comp.inputs['Image'])

    bpy.ops.render.render()
    test_path = os.path.join(tempfile.gettempdir(), f'test_{cs_name}.exr')
    rr.save_render(test_path, scene=scene)

    loaded = bpy.data.images.load(test_path)
    loaded_pixels = np.empty(64*64*4, dtype=np.float32)
    loaded.pixels.foreach_get(loaded_pixels)
    bpy.data.images.remove(loaded)
    bpy.data.images.remove(test_img)
    tree.nodes.remove(img_node)

    print(f"Image Node with colorspace '{cs_name}' -> Composite:")
    print(f"  min: {loaded_pixels.min():.5f} max: {loaded_pixels.max():.5f} mean: {loaded_pixels.mean():.5f}")
    print(f"  diff from baseline mean: {np.abs(loaded_pixels - base_pixels).mean():.5f}")
