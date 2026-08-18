"""Process hair in isolation: apply anime-style smoothing + solidify."""
import bpy
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "hair_only.blend"))

hair = bpy.data.objects.get("part_2.001")
print(f"Hair: {hair.name}, verts={len(hair.data.vertices)}")

# Set up scene
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True

# Step 1: Smooth shading
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.shade_smooth()
hair.select_set(False)
print("  Shade smooth applied")

# Step 2: Add solidify (1.5mm wall thickness for 3D print)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
print("  Solidify modifier added (1.5mm)")

# Step 3: Add Subdivision Surface (Catmull-Clark for anime curves)
mod_sub = hair.modifiers.new("AnimeSubdivision", "SUBSURF")
mod_sub.subdivision_type = "CATMULL_CLARK"
mod_sub.levels = 1  # viewport
mod_sub.render_levels = 2  # render
print("  Subdivision modifier added (catmull-clark 1/2)")

# Step 4: Apply solidify (bake into mesh)
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
try:
    bpy.ops.object.modifier_apply(modifier="PrintSolidify")
    print("  Solidify applied")
except Exception as e:
    print(f"  WARN: solidify apply failed: {e}")

# Don't apply subdivision (keep as modifier for viewport/render control)
# But the modifier is now active and would be evaluated at render time

# Set up anime material
hair.data.materials.clear()
mat = bpy.data.materials.new("AFR_HairMat_Anime")
mat.use_nodes = True
mat.node_tree.nodes.clear()
out_n = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.93, 0.93, 0.96, 1.0)  # silvery
bsdf.inputs["Roughness"].default_value = 0.35
bsdf.inputs["Metallic"].default_value = 0.0
# Try setting sheen (Blender 5.x API)
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
print("  Anime material set (with Sheen for anime hair)")

# Save the result
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime.blend"))
print(f"\nSaved hair_anime.blend")
print(f"  verts after solidify: {len(hair.data.vertices)}")
print(f"  modifiers remaining: {[m.name for m in hair.modifiers]}")
