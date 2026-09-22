import bpy
import sys
import time

def log(msg):
    print(msg)
    sys.stdout.flush()

log("[GUI Rounds] Addon loading...")
addon_dir = r"d:\1\dlls5 for blender"
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)
import dlss5_blender
dlss5_blender.register()
from dlss5_blender.core.image_processor import get_scene_compositor_tree

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100

bpy.ops.scene.dlss5_setup_compositor()
log("[GUI Rounds] Setup compositor done.")

round_state = {"current": 0, "max": 5}

def do_render_round():
    round_state["current"] += 1
    r = round_state["current"]
    log(f"\n>>> ROUND {r} START <<<")
    
    tree = get_scene_compositor_tree(bpy.context.scene)
    comp = None
    viewer = None
    for n in tree.nodes:
        if n.bl_idname in {'CompositorNodeComposite', 'NodeGroupOutput'}:
            comp = n
        elif n.bl_idname == 'CompositorNodeViewer':
            viewer = n
    out_node = tree.nodes.get("DLSS5_Image_Output")
    
    comp_in = comp.inputs.get('Image') if comp and 'Image' in comp.inputs else (comp.inputs[0] if comp and comp.inputs else None)
    comp_links = [lk.from_node.name + '.' + lk.from_socket.name for lk in comp_in.links] if comp_in else []
    viewer_links = [lk.from_node.name + '.' + lk.from_socket.name for lk in viewer.inputs['Image'].links] if viewer and 'Image' in viewer.inputs else []
    log(f"[Round {r} BEFORE F12] Comp links: {comp_links}")
    log(f"[Round {r} BEFORE F12] Viewer links: {viewer_links}")
    
    bpy.ops.render.render('INVOKE_DEFAULT')
    
    # Wait for job to finish: give at least 0.5s before polling is_job_running
    def poll_job():
        if hasattr(bpy.app, 'is_job_running') and bpy.app.is_job_running('RENDER'):
            return 0.2
        
        log(f"[Round {r}] Render job completed by Blender.")
        
        # Now wait for deferred timers (on_render_post deferred timer runs at first_interval=0.01)
        wait_timer = [0]
        def poll_dlss():
            wait_timer[0] += 1
            cur_scene = bpy.context.scene
            cur_tree = get_scene_compositor_tree(cur_scene)
            cur_node = None
            if cur_tree:
                for n in cur_tree.nodes:
                    if n.bl_idname == 'CompositorNodeDLSS5':
                        cur_node = n
                        break
            
            status = cur_node.last_status if cur_node else "None"
            log(f"[Round {r} poll {wait_timer[0]}] DLSS5 status: '{status}'")
            
            # Check links
            c_links = [lk.from_node.name for lk in comp_in.links] if comp_in else []
            v_links = [lk.from_node.name for lk in viewer.inputs['Image'].links] if viewer and 'Image' in viewer.inputs else []
            
            out_img = bpy.data.images.get("DLSS5_Output")
            p_mean = None
            if out_img:
                arr = [0.0] * min(100, out_img.size[0] * out_img.size[1] * 4)
                # quick sample
                p_mean = out_img.size[:]
            
            if "完成" in status and any(x in c_links for x in ["DLSS5 Neural Rendering", "DLSS5_Image_Output"]):
                log(f"[Round {r} SUCCESS] DLSS5 finished and linked! Comp: {c_links}, Viewer: {v_links}, Image size: {p_mean}")
                if r < round_state["max"]:
                    # Wait 1.0s before starting next round
                    bpy.app.timers.register(do_render_round, first_interval=1.0)
                else:
                    log(f"\n[GUI Rounds] ALL {round_state['max']} ROUNDS SUCCESSFUL! Quitting.")
                    bpy.ops.wm.quit_blender()
                return None
            
            if wait_timer[0] >= 30: # 3 seconds timeout
                log(f"[Round {r} FAILED] Timeout waiting for DLSS5 completion or link! Status: '{status}', Comp links: {c_links}, Viewer links: {v_links}")
                log("[GUI Rounds] FAILED! Quitting.")
                bpy.ops.wm.quit_blender()
                return None
                
            return 0.1

        bpy.app.timers.register(poll_dlss, first_interval=0.2)
        return None

    bpy.app.timers.register(poll_job, first_interval=0.5)
    return None

bpy.app.timers.register(do_render_round, first_interval=1.0)
