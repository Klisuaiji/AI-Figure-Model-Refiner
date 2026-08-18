"""Hair: use Laplacian smoothing (bmesh) + solidify. Lighter than subdiv."""
import bpy
import bmesh
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "hair_only.blend"))

hair = bpy.data.objects.get("part_2.001")
print(f"Hair start: {len(hair.data.vertices)} verts")

# Step 1: Laplacian smooth using bmesh (3 iterations for anime smoothness)
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.shade_smooth()
hair.select_set(False)

for i in range(3):
    bm = bmesh.new()
    try:
        bm.from_mesh(hair.data)
        bmesh.ops.smooth_vert(
            bm, verts=list(bm.verts),
            factor=0.3,
            use_axis_x=True, use_axis_y=True, use_axis_z=True,
        )
        bm.to_mesh(hair.data)
    finally:
        bm.free()
    print(f"  Laplacian iteration {i+1} done, verts={len(hair.data.vertices)}")
hair.data.update()

# Step 2: Solidify 1.5mm (apply modifier)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True

bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.modifier_apply(modifier="PrintSolidify")
hair.select_set(False)
print(f"  Solidify applied, verts={len(hair.data.vertices)}")

# Step 3: Anime material
hair.data.materials.clear()
mat = bpy.data.materials.new("AFR_HairMat_Anime")
mat.use_nodes = True
mat.node_tree.nodes.clear()
out_n = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.93, 0.93, 0.96, 1.0)
bsdf.inputs["Roughness"].default_value = 0.35
bsdf.inputs["Metallic"].default_value = 0.0
try:
    bsdf.inputs["Sheen Weight"].default_value = 0.7
except KeyError:
    pass
mat.node_tree.links.new(bsdf.outputs["BSDF"], out_n.inputs["Surface"])
hair.data.materials.append(mat)
attrs = list(hair.data.color_attributes.keys())
for an in attrs:
    hair.data.color_attributes.remove(hair.data.color_attributes[an])
hair.data.color_attributes.render_color_index = -1

# Save
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime.blend"))
print(f"Saved hair_anime.blend")

# Render
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
