"""Position all parts at the figure's location, then render."""
import bpy
import bmesh
from mathutils import Vector
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "figure_anime.blend"))

# Identify which parts are at (0,0,0) — these are the user's newly added parts
new_parts = []
old_parts = []
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    if o.name.startswith("Mesh_") or o.name in {"Light", "Camera"}:
        continue
    if abs(o.location.x) < 0.01 and abs(o.location.y) < 0.01 and abs(o.location.z) < 0.01:
        new_parts.append(o)
    else:
        old_parts.append(o)
print(f"new parts (at origin): {[p.name for p in new_parts]}")
print(f"old parts (at figure pos): {[p.name for p in old_parts]}")

# Figure center (the old parts are at 1.47, 0, 0)
fig_center = Vector((1.47, 0.0, 0.0))

# For each new part, move it to the figure position
# Use a simple offset based on local bbox
for p in new_parts:
    # Just translate to fig_center
    p.location = fig_center
    print(f"  moved {p.name} to {p.location}")

# Save
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "figure_anime_assembled.blend"))
print("Saved figure_anime_assembled.blend")

# Setup render
bpy.context.scene.world.use_nodes = True
bpy.context.scene.world.node_tree.nodes.clear()
bgn = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeBackground")
bgn.inputs["Color"].default_value = (0.4, 0.4, 0.42, 1.0)
bgn.inputs["Strength"].default_value = 0.5
out_n = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeOutputWorld")
bpy.context.scene.world.node_tree.links.new(bgn.outputs["Background"], out_n.inputs["Surface"])

if not any(o.type == "LIGHT" for o in bpy.data.objects):
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 4.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)
if not any(o.type == "CAMERA" for o in bpy.data.objects):
    bpy.ops.object.camera_add(location=(0, -3, 1))
    bpy.context.scene.camera = bpy.context.view_layer.objects.active

bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"

# Hide decorations for the figure-only render
for o in bpy.data.objects:
    if o.name.startswith("Mesh_"):
        o.hide_render = True
        o.hide_viewport = True

# Render the figure (all part_X and part_X.001)
all_mesh = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("Mesh_") and not o.hide_render]
bb_all = []
for o in all_mesh:
    for c in o.bound_box:
        bb_all.append(o.matrix_world @ Vector(c))
center = sum(bb_all, Vector((0, 0, 0))) / len(bb_all)
size = max(max(p[i] for p in bb_all) - min(p[i] for p in bb_all) for i in range(3))
print(f"\nFrame: center={center}, size={size}")

cam = bpy.context.scene.camera
for view_name, view_offset in [
    ("diag", (size * 1.0, -size * 1.0, size * 0.5)),
    ("front", (0, -size * 1.6, 0)),
    ("back", (0, size * 1.6, 0)),
]:
    cam.location = (center.x + view_offset[0],
                    center.y + view_offset[1],
                    center.z + view_offset[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"figure_assembled_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved figure_assembled_{view_name}.png")

# ========================================================
# Render WITH decorations
# ========================================================
print("\n=== Render WITH decorations ===")
# Show decorations
for o in bpy.data.objects:
    if o.name.startswith("Mesh_"):
        o.hide_render = False
        o.hide_viewport = False
# Position decoration1 (Mesh_0) and decoration2 (Mesh_0.001) on either side
dec1 = bpy.data.objects.get("Mesh_0")
dec2 = bpy.data.objects.get("Mesh_0.001")
if dec1:
    dec1.location = (center.x - size * 0.8, center.y, center.z + size * 0.2)
    dec1.scale = (0.5, 1.0, 0.5)
    # Clean materials
    dec1.data.materials.clear()
    mat = bpy.data.materials.new("AFR_Dec1_Anime")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out_n = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.85, 0.65, 0.30, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Metallic"].default_value = 0.7
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out_n.inputs["Surface"])
    dec1.data.materials.append(mat)
    attrs = list(dec1.data.color_attributes.keys())
    for an in attrs:
        dec1.data.color_attributes.remove(dec1.data.color_attributes[an])
    dec1.data.color_attributes.render_color_index = -1
if dec2:
    dec2.location = (center.x + size * 0.8, center.y, center.z + size * 0.1)
    dec2.scale = (0.5, 0.5, 0.5)
    dec2.data.materials.clear()
    mat = bpy.data.materials.new("AFR_Dec2_Anime")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out_n = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.20, 0.45, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out_n.inputs["Surface"])
    dec2.data.materials.append(mat)
    attrs = list(dec2.data.color_attributes.keys())
    for an in attrs:
        dec2.data.color_attributes.remove(dec2.data.color_attributes[an])
    dec2.data.color_attributes.render_color_index = -1

# Re-frame
all_mesh = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
bb_all = []
for o in all_mesh:
    for c in o.bound_box:
        bb_all.append(o.matrix_world @ Vector(c))
center = sum(bb_all, Vector((0, 0, 0))) / len(bb_all)
size = max(max(p[i] for p in bb_all) - min(p[i] for p in bb_all) for i in range(3))

for view_name, view_offset in [
    ("with_dec_diag", (size * 1.0, -size * 1.0, size * 0.5)),
    ("with_dec_front", (0, -size * 1.6, 0)),
]:
    cam.location = (center.x + view_offset[0],
                    center.y + view_offset[1],
                    center.z + view_offset[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"figure_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved figure_{view_name}.png")

# Save
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "figure_anime_with_dec.blend"))
print("Saved figure_anime_with_dec.blend")
