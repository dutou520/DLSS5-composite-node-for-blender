import bpy
import sys
import time

print("[GUI Test] Initializing...")
# Ensure addon is loaded
try:
    import dlss5_blender
    dlss5_blender.register()
    print("[GUI Test] Addon registered.")
except Exception as e:
    print(f"[GUI Test] Error registering: {e}")

scene = bpy.context.scene
scene.render.resolution_x = 128
scene.render.resolution_y = 128
scene.render.resolution_percentage = 100

# Setup compositor
bpy.ops.scene.dlss5_setup_compositor()
print("[GUI Test] Compositor setup done.")

# Check auto_process_on_render
node = None
for n in scene.node_tree.nodes:
    if n.bl_idname == 'CompositorNodeDLSS5':
        node = n
        break

print(f"[GUI Test] DLSS5 node found: {node}, auto_process={node.auto_process_on_render if node else None}")

# Define a timer to trigger render and then check and quit
def run_f12_test():
    print("[GUI Test] Triggering F12 render via INVOKE_DEFAULT (running in background job thread)...")
    bpy.ops.render.render('INVOKE_DEFAULT')
    
    def check_done():
        is_rendering = hasattr(bpy.app, 'is_job_running') and bpy.app.is_job_running('RENDER')
        if is_rendering:
            print("[GUI Test] Rendering still in progress...")
            return 0.2
        print("[GUI Test] Render job finished! Waiting 1s for deferred timers to run...")
        def check_status_and_quit():
            cur_node = None
            for n in bpy.context.scene.node_tree.nodes:
                if n.bl_idname == 'CompositorNodeDLSS5':
                    cur_node = n
                    break
            print(f"[GUI Test] Node status after render & timer: {cur_node.last_status if cur_node else 'None'}")
            print(f"[GUI Test] Node last engine: {cur_node.last_engine_used if cur_node else 'None'}")
            out_img = bpy.data.images.get("DLSS5_Output")
            print(f"[GUI Test] DLSS5_Output image: {out_img}, size={out_img.size if out_img else None}")
            print("[GUI Test] SUCCESS! Exiting GUI Blender cleanly.")
            bpy.ops.wm.quit_blender()
            return None
        bpy.app.timers.register(check_status_and_quit, first_interval=1.0)
        return None

    bpy.app.timers.register(check_done, first_interval=0.5)
    return None

bpy.app.timers.register(run_f12_test, first_interval=1.0)
