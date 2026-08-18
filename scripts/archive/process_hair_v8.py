"""V8: Hybrid — shrinkwrap for the base mass + sculpt-asymmetric for hair flow.

Approach:
1. Pre-smooth hair to remove spikes
2. Shrinkwrap a higher-poly sphere to the hair (more contour detail)
3. Add some sculpting-like displacement for hair asymmetry
4. Solidify 1.5mm
5. Toon material
"""
import bpy
import bmesh
from mathutils import Vector, Matrix
import os
import random

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
# STEP 1: Pre-smooth the original hair to get a smoother target
# ------------------------------------------------------------------
print("\n=== STEP 1: Pre-smooth hair (3 iter factor 0.10) ===")
for i in range(3):
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
print(f"  Pre-smooth: dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 2: Create higher-poly sphere for shrinkwrap
# ------------------------------------------------------------------
print("\n=== STEP 2: Create higher-poly sphere ===")
bb = [hair.matrix_world @ Vector(c) for c in hair.bound_box]
center = sum(bb, Vector((0, 0, 0))) / 8.0
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
print(f"  center: {center}, size: {size}")

bpy.ops.mesh.primitive_uv_sphere_add(
    radius=size * 1.5,  # BIGGER than hair, so it can fully encompass
    segments=24,
    ring_count=16,
    location=(center.x, center.y, center.z),
)
sphere = bpy.context.view_layer.objects.active
sphere.name = "AFR_ShrinkwrapMesh"
# Scale elongated to match hair
sphere.scale = (0.9, 0.7, 0.9)  # slightly squished
print(f"  Sphere: v={len(sphere.data.vertices)}, dims={sphere.dimensions}")

# ------------------------------------------------------------------
# STEP 3: Shrinkwrap
# ------------------------------------------------------------------
print("\n=== STEP 3: Shrinkwrap to hair ===")
bpy.context.view_layer.objects.active = sphere
sphere.select_set(True)
mod_sw = sphere.modifiers.new("Shrinkwrap", "SHRINKWRAP")
mod_sw.target = hair
mod_sw.wrap_method = 'PROJECT'
mod_sw.project_limit = 1.0
mod_sw.use_negative_direction = True
mod_sw.use_positive_direction = True
mod_sw.cull_face = 'OFF'
bpy.ops.object.modifier_apply(modifier="Shrinkwrap")
sphere.select_set(False)
print(f"  Shrinkwrap: v={len(sphere.data.vertices)}, dims={sphere.dimensions}")

# ------------------------------------------------------------------
# STEP 4: Add asymmetric displacement (hair-flow hints)
# ------------------------------------------------------------------
print("\n=== STEP 4: Asymmetric displacement (downward elongation) ===")
# Pull the bottom of the sphere down (longer hair on bottom)
bm = bmesh.new()
try:
    bm.from_mesh(sphere.data)
    rng = random.Random(42)
    for v in bm.verts:
        # Pull bottom verts down to create "flowing hair" silhouette
        local_z = v.co.z
        # Scale the bottom: if z < center_z, push down
        if local_z < 0:
            v.co.z = local_z * 1.3
        # Add subtle random perturbation
        v.co.x += rng.uniform(-0.005, 0.005)
        v.co.y += rng.uniform(-0.005, 0.005)
    bm.to_mesh(sphere.data)
finally:
    bm.free()
sphere.data.update()
print(f"  After displacement: dims={sphere.dimensions}")

# ------------------------------------------------------------------
# STEP 5: Smooth the result
# ------------------------------------------------------------------
print("\n=== STEP 5: Final smoothing ===")
for i in range(3):
    bm = bmesh.new()
    try:
        bm.from_mesh(sphere.data)
        bmesh.ops.smooth_vert(
            bm, verts=list(bm.verts),
            factor=0.15,
            use_axis_x=True, use_axis_y=True, use_axis_z=True,
        )
        bm.to_mesh(sphere.data)
    finally:
        bm.free()
    sphere.data.update()
print(f"  After smooth: dims={sphere.dimensions}")

# ------------------------------------------------------------------
# STEP 6: Solidify
# ------------------------------------------------------------------
print("\n=== STEP 6: Solidify 1.5mm ===")
bpy.context.view_layer.objects.active = sphere
sphere.select_set(True)
mod_sol = sphere.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
bpy.ops.object.modifier_apply(modifier="PrintSolidify")
sphere.select_set(False)
print(f"  Solidify: v={len(sphere.data.vertices)}, dims={sphere.dimensions}")

# Hide original
hair.hide_render = True
hair.hide_viewport = True
sphere.name = "part_2.001"

# ------------------------------------------------------------------
# STEP 7: Toon material
# ------------------------------------------------------------------
print("\n=== STEP 7: Toon material ===")
sphere.data.materials.clear()
mat = bpy.data.materials.new("AFR_HairMat_Toon")
mat.use_nodes = True
mat.node_tree.nodes.clear()
output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfDiffuse")
bsdf.inputs["Color"].default_value = (0.85, 0.85, 0.88, 1.0)
shader_to_rgb = mat.node_tree.nodes.new("ShaderNodeShaderToRGB")
mat.node_tree.links.new(bsdf.outputs["BSDF"], shader_to_rgb.inputs["Shader"])
color_ramp = mat.node_tree.nodes.new("ShaderNodeValToRGB")
elements = color_ramp.color_ramp.elements
elements[0].position = 0.30
elements[0].color = (0.35, 0.35, 0.40, 1.0)
elements[1].position = 0.50
elements[1].color = (0.75, 0.75, 0.80, 1.0)
hl = elements.new(0.85)
hl.color = (0.98, 0.98, 1.0, 1.0)
mat.node_tree.links.new(shader_to_rgb.outputs["Color"], color_ramp.inputs["Fac"])
emission = mat.node_tree.nodes.new("ShaderNodeEmission")
mat.node_tree.links.new(color_ramp.outputs["Color"], emission.inputs["Color"])
mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
sphere.data.materials.append(mat)
attrs = list(sphere.data.color_attributes.keys())
for an in attrs:
    sphere.data.color_attributes.remove(sphere.data.color_attributes[an])
sphere.data.color_attributes.render_color_index = -1

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime_v8.blend"))
print(f"\nSaved hair_anime_v8.blend")

# Render
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"

bb = [sphere.matrix_world @ Vector(c) for c in sphere.bound_box]
center = sum(bb, Vector((0, 0, 0))) / 8.0
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))

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
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_v8_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_v8_{view_name}.png")
