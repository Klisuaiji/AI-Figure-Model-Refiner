"""Render animed hair at closer view to see the detail."""
import bpy
import bmesh
from mathutils import Vector, Matrix
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime.blend"))

hair = bpy.data.objects.get("part_2.001")
print(f"Hair: {hair.name}, verts={len(hair.data.vertices)}")

# IMPORTANT: set the hair at origin for clear viewing
# (current location is (1.47, 0, 0))
# Get the hair's center
bb_local = [Vector(c) for c in hair.bound_box]
center_local = sum(bb_local, Vector((0, 0, 0))) / 8.0
print(f"  bbox local center: {center_local}")
# Move hair so its center is at world origin
hair.location = (0, 0, 0)
# Apply translation to bake
bm = bmesh.new()
try:
    bm.from_mesh(hair.data)
    # translate by -world_center (negative of position)
    world_center = hair.matrix_world @ center_local
    bm.transform(Matrix.Translation(Vector((-world_center.x, -world_center.y, -world_center.z))))
    bm.to_mesh(hair.data)
finally:
    bm.free()
hair.data.update()
print(f"  moved hair to origin")

# Re-setup
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"

# Center the camera closer
bb = [hair.matrix_world @ Vector(c) for c in hair.bound_box]
center = sum(bb, Vector((0, 0, 0))) / 8.0
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
print(f"  hair size: {size}, center: {center}")

cam = bpy.context.scene.camera
for view_name, view_offset in [
    ("diag", (size * 0.8, -size * 0.8, size * 0.5)),
    ("front", (0, -size * 1.4, 0)),
    ("side", (size * 1.4, 0, 0)),
    ("close", (size * 0.5, -size * 0.5, size * 0.3)),
]:
    cam.location = (center.x + view_offset[0],
                    center.y + view_offset[1],
                    center.z + view_offset[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50  # tighter
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_animed_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_animed_{view_name}.png")
