import bpy

scene = bpy.context.scene
scene.render.resolution_x = 64
scene.render.resolution_y = 64
bpy.ops.render.render()

rr = bpy.data.images.get("Render Result")
print("Render Result attributes:")
print("  has_data:", getattr(rr, "has_data", None))
print("  type:", getattr(rr, "type", None))
print("  source:", getattr(rr, "source", None))
print("  layers:", [l.name for l in rr.render_slots])
for slot in rr.render_slots:
    print("  slot:", slot.name)
if hasattr(rr, "layers"):
    for layer in rr.layers:
        print("  layer:", layer.name)
        for p in layer.passes:
            print("    pass:", p.name, p.channels)
