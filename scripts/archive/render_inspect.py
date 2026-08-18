"""Render multiple views of D:\未命名.blend: whole scene + each object isolated."""
import bpy
import os
import sys

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\unnamed_inspect"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

# Make sure we have a camera, set up simple lighting
if "Camera" not in bpy.data.objects:
    cam_data = bpy.data.cameras.new("Cam")
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

# Add a sun + ambient if missing
if "Light" not in bpy.data.objects:
    light_data = bpy.data.lights.new("Sun", type="SUN")
    light_data.energy = 5.0
    light_obj = bpy.data.objects.new("Sun", light_data)
    bpy.context.scene.collection.objects.link(light_obj)

# Use eevee for speed
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 16
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.context.scene.view_settings.view_transform = "Standard"


def frame_object(obj, distance_factor=1.5):
    """Point camera at object from a set distance."""
    cam = bpy.context.scene.camera
    # Use object's bounding box center in world space
    bb = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center = sum(bb, Vector((0, 0, 0))) / 8.0
    size = max((max(c[i] for c in bb) - min(c[i] for c in bb)) for i in range(3))
    dist = max(1.0, size * distance_factor)
    cam.location = (center.x + dist, center.y - dist, center.z + dist * 0.7)
    cam.data.lens = 50
    direction = center - cam.location
    rot = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()
    # Update view transforms
    bpy.context.view_layer.update()


def render_scene(filename, only_objs=None):
    """Render the scene. If only_objs provided, hide all others."""
    if only_objs is not None:
        all_names = {o.name for o in bpy.data.objects}
        for o in bpy.data.objects:
            o.hide_render = (o.name not in only_objs)
    else:
        for o in bpy.data.objects:
            o.hide_render = False
    path = os.path.join(OUT_DIR, filename)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


from mathutils import Vector

# Render full scene first
print("Rendering full scene...")
all_objs = [o.name for o in bpy.data.objects if o.type == "MESH"]
print("MESH objects:", all_objs)

# Set camera to view the whole scene
cam = bpy.context.scene.camera
all_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if all_meshes:
    bbs = []
    for o in all_meshes:
        bb = [o.matrix_world @ Vector(corner) for corner in o.bound_box]
        bbs.append(bb)
    all_corners = sum(bbs, [])
    cx = sum(c.x for c in all_corners) / len(all_corners)
    cy = sum(c.y for c in all_corners) / len(all_corners)
    cz = sum(c.z for c in all_corners) / len(all_corners)
    center = Vector((cx, cy, cz))
    max_size = max(max((max(p[i] for p in all_corners) - min(p[i] for p in all_corners)) for i in range(3)), 1.0)
    dist = max_size * 2.0
    cam.location = (center.x + dist * 0.5, center.y - dist * 1.5, center.z + dist * 0.7)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35

bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "00_full_scene.png")
bpy.ops.render.render(write_still=True)
print("Wrote 00_full_scene.png")

# Render each object individually
for name in all_objs:
    obj = bpy.data.objects.get(name)
    if obj is None:
        continue
    print(f"Rendering {name}...")
    # Hide all, show only this one
    for o in bpy.data.objects:
        o.hide_render = (o.name != name)
    frame_object(obj)
    out = os.path.join(OUT_DIR, f"obj_{name.replace(' ', '_').replace('.', '_')}.png")
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)

print("All renders done")
print("OUT_DIR:", OUT_DIR)
