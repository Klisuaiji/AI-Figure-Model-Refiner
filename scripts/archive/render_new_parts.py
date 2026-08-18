"""Render each part_X (newly added by user) to identify what they are."""
import bpy
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\unnamed_inspect_v2"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 16
bpy.context.scene.render.resolution_x = 400
bpy.context.scene.render.resolution_y = 400
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"

# Add sun light
if "Sun" not in bpy.data.objects:
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 3.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)
bpy.context.scene.world.use_nodes = True
bgn = bpy.context.scene.world.node_tree.nodes.get("Background")
if bgn:
    bgn.inputs["Color"].default_value = (0.3, 0.3, 0.32, 1.0)
    bgn.inputs["Strength"].default_value = 0.5

# For each part, render
new_parts = sorted([o for o in bpy.data.objects
                    if o.name.startswith("part_") and not o.name.endswith(".001")],
                   key=lambda o: int(o.name.split("_")[1]))
print(f"New parts to render: {[p.name for p in new_parts]}")

for p in new_parts:
    # Hide all other MESH objects
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = (o is not p)
            o.hide_viewport = (o is not p)
    # Frame on p
    bb = [p.matrix_world @ Vector(c) for c in p.bound_box]
    c = sum(bb, Vector((0, 0, 0))) / 8.0
    s = max(max(pp[i] for pp in bb) - min(pp[i] for pp in bb) for i in range(3))
    if bpy.context.scene.camera is None or bpy.context.scene.camera.name == "Camera":
        bpy.ops.object.camera_add(location=(c.x, c.y - s * 1.5, c.z + s * 0.1))
        bpy.context.scene.camera = bpy.context.view_layer.objects.active
    cam = bpy.context.scene.camera
    cam.location = (c.x, c.y - s * 1.5, c.z + s * 0.1)
    direction = c - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    out = os.path.join(OUT_DIR, f"{p.name}_diag.png")
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print(f"  {p.name} (v={len(p.data.vertices)}, dim={list(p.dimensions)}): {out}")
