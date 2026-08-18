"""V2: Anime-stylized hair — single unified mass (NOT tentacle strands).

From yelzkizi guide + sekouperry principles:
1. DECIMATE heavily to remove isolated thin strands
2. Smooth (Laplacian) to unify surface
3. Solidify 1.5mm for 3D print wall
4. TAPER TIPS to points (anime-style sharp ends, not rounded tubes)
5. Toon material (flat + 2-step cel shading) for unified look
"""
import bpy
import bmesh
from mathutils import Vector
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow_v2"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow\hair_only.blend")

hair = bpy.data.objects.get("part_2.001")
print(f"Hair start: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# Setup world + sun
bpy.context.scene.world.use_nodes = True
bpy.context.scene.world.node_tree.nodes.clear()
bgn = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeBackground")
bgn.inputs["Color"].default_value = (0.4, 0.4, 0.42, 1.0)
bgn.inputs["Strength"].default_value = 0.6
out_n = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeOutputWorld")
bpy.context.scene.world.node_tree.links.new(bgn.outputs["Background"], out_n.inputs["Surface"])

if not any(o.type == "LIGHT" for o in bpy.data.objects):
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 5.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)
if not any(o.type == "CAMERA" for o in bpy.data.objects):
    bpy.ops.object.camera_add(location=(0, -3, 1))
    bpy.context.scene.camera = bpy.context.view_layer.objects.active

# ------------------------------------------------------------------
# STEP 1: Decimate heavily to remove spaghetti strands
# ------------------------------------------------------------------
print("\n=== STEP 1: Decimate (remove isolated strands) ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_dec = hair.modifiers.new("Decimate", "DECIMATE")
mod_dec.ratio = 0.08  # keep 8% → ~15k verts
mod_dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="Decimate")
hair.select_set(False)
print(f"  After decimate: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 2: Gentle Laplacian smooth (factor 0.10, 2 iters)
# ------------------------------------------------------------------
print("\n=== STEP 2: Gentle Laplacian smoothing ===")
for it in range(2):
    bm = bmesh.new()
    try:
        bm.from_mesh(hair.data)
        bmesh.ops.smooth_vert(
            bm, verts=list(bm.verts),
            factor=0.10,
            use_axis_x=True, use_axis_y=True, use_axis_z=True,
        )
        bm.to_mesh(hair.data)
    finally:
        bm.free()
    hair.data.update()
print(f"  After smooth: dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 3: Solidify 1.5mm for 3D print wall thickness
# ------------------------------------------------------------------
print("\n=== STEP 3: Solidify 1.5mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
bpy.ops.object.modifier_apply(modifier="PrintSolidify")
hair.select_set(False)
print(f"  After solidify: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 4: TAPER TIPS — find the lowest-z vertices (hair tips) and
# pinch them together. This converts rounded tube ends into pointed
# anime-style tips.
# ------------------------------------------------------------------
print("\n=== STEP 4: Taper tips to points ===")
bm = bmesh.new()
try:
    bm.from_mesh(hair.data)
    # Find all "loose" vertices (boundary verts with very few connections)
    # These are likely the hair tips
    # We use a different approach: find the topmost AND bottommost extremes
    # in local Z, and pinch them.
    # For anime hair on a head, the tips are the BOTTOMMOST points.
    # Get the topmost point (likely the crown/root)
    all_verts = list(bm.verts)
    z_values = [v.co.z for v in all_verts]
    z_max = max(z_values)
    z_min = min(z_values)
    z_range = z_max - z_min
    # The bottom 25% are likely tips (where hair flows down)
    tip_threshold = z_min + z_range * 0.25
    tip_verts = [v for v in all_verts if v.co.z < tip_threshold]
    print(f"  {len(tip_verts)} tip vertices found (bottom 25%)")
    if tip_verts:
        # Compute centroid of tips
        tip_centroid = Vector((0, 0, 0))
        for v in tip_verts:
            tip_centroid += v.co
        tip_centroid /= len(tip_verts)
        # Taper: move each tip vertex 40% towards the centroid
        # This makes them cluster together (creating pointed tips)
        for v in tip_verts:
            direction = tip_centroid - v.co
            v.co = v.co + direction * 0.4
        bm.to_mesh(hair.data)
        print(f"  Tips tapered 40% towards centroid")
finally:
    bm.free()
hair.data.update()
print(f"  After taper: dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 5: TOON material — Shader to RGB + ColorRamp for cel-shaded
# unified mass look. This is the yelzkizi technique.
# ------------------------------------------------------------------
print("\n=== STEP 5: Toon material (cel-shaded) ===")
hair.data.materials.clear()
mat = bpy.data.materials.new("AFR_HairMat_Toon")
mat.use_nodes = True
mat.node_tree.nodes.clear()
out_n = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")

# Path: TextureCoord → (skip; flat color) → BSDF → Shader to RGB → ColorRamp → BSDF
# Or simpler: Principled → Shader to RGB → ColorRamp → Diffuse

# Use the cel-shading approach (yelzkizi):
# Principled BSDF with high lightness, then Shader to RGB, then ColorRamp (2 steps)
bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Base Color"].default_value = (0.93, 0.93, 0.96, 1.0)  # silver
bsdf.inputs["Roughness"].default_value = 0.6
bsdf.inputs["Metallic"].default_value = 0.0
try:
    bsdf.inputs["Sheen Weight"].default_value = 0.7
    bsdf.inputs["Sheen Tint"].default_value = (0.85, 0.85, 0.95, 1.0)
except KeyError:
    pass

shader_to_rgb = mat.node_tree.nodes.new("ShaderNodeShaderToRGB")
mat.node_tree.links.new(bsdf.outputs["BSDF"], shader_to_rgb.inputs["Shader"])

color_ramp = mat.node_tree.nodes.new("ShaderNodeValToRGB")
color_ramp.color_ramp.elements[0].position = 0.3
color_ramp.color_ramp.elements[0].color = (0.10, 0.10, 0.12, 1)  # shadow
color_ramp.color_ramp.elements[1].position = 0.5
color_ramp.color_ramp.elements[1].color = (0.75, 0.75, 0.78, 1)  # mid
# Add a 3rd element for the highlight
highlight = color_ramp.color_ramp.elements.new(0.85)
highlight.color = (0.98, 0.98, 1.0, 1)  # highlight
mat.node_tree.links.new(shader_to_rgb.outputs["Color"], color_ramp.inputs["Fac"])

# Final emission (cel-shaded look: matte color × ramp)
emission = mat.node_tree.nodes.new("ShaderNodeEmission")
emission.inputs["Color"].default_value = (0.93, 0.93, 0.96, 1)  # silver base
mat.node_tree.links.new(color_ramp.outputs["Color"], emission.inputs["Color"])

mat.node_tree.links.new(emission.outputs["Emission"], out_n.inputs["Surface"])

# Mix with a tiny amount of principled for sheen
mix_shader = mat.node_tree.nodes.new("ShaderNodeMixShader")
mix_shader.inputs["Fac"].default_value = 0.7
mat.node_tree.links.new(emission.outputs["Emission"], mix_shader.inputs[1])
mat.node_tree.links.new(bsdf.outputs["BSDF"], mix_shader.inputs[2])
mat.node_tree.links.new(mix_shader.outputs["Shader"], out_n.inputs["Surface"])

hair.data.materials.append(mat)
attrs = list(hair.data.color_attributes.keys())
for an in attrs:
    hair.data.color_attributes.remove(hair.data.color_attributes[an])
hair.data.color_attributes.render_color_index = -1
print(f"  Toon material set up (cel-shaded with 3-step ColorRamp)")

# Save
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime_v2.blend"))
print(f"\nSaved hair_anime_v2.blend")

# ------------------------------------------------------------------
# RENDER
# ------------------------------------------------------------------
print("\n=== Render ===")
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
print(f"hair size: {size}, center: {center}")

cam = bpy.context.scene.camera
for view_name, view_offset in [
    ("diag", (size * 0.8, -size * 0.8, size * 0.5)),
    ("front", (0, -size * 1.4, 0)),
    ("side", (size * 1.4, 0, 0)),
]:
    cam.location = (center.x + view_offset[0],
                    center.y + view_offset[1],
                    center.z + view_offset[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 40
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_v2_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_v2_{view_name}.png")
