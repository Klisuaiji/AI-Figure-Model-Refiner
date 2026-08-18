"""Apply subdivision to bake, then render."""
import bpy
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime.blend"))

hair = bpy.data.objects.get("part_2.001")
print(f"Hair: {hair.name}, verts={len(hair.data.vertices)}, mods={[m.name for m in hair.modifiers]}")

# Apply subdivision (this bakes the smooth into the mesh)
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
try:
    bpy.ops.object.modifier_apply(modifier="AnimeSubdivision")
    print(f"  Subdivision applied. Verts: {len(hair.data.vertices)}")
except Exception as e:
    print(f"  Apply failed: {e}")
hair.select_set(False)

# Save the baked version
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime_baked.blend"))
print(f"Saved hair_anime_baked.blend")

# Setup render
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"

bb = [hair.matrix_world @ Vector(c) for c in hair.bound_box]
center = sum(bb, Vector((0, 0, 0))) / 8.0
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))

cam = bpy.context.scene.camera
for view_name, view_offset in [
    ("diag", (size * 1.0, -size * 1.0, size * 0.5)),
    ("front", (0, -size * 1.8, 0)),
    ("side", (size * 1.8, 0, 0)),
]:
    cam.location = (center.x + view_offset[0],
                    center.y + view_offset[1],
                    center.z + view_offset[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_animed_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_animed_{view_name}.png")
