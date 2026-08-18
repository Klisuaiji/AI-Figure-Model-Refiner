"""V4: Clean approach without voxel remesh.

Steps:
1. Strong decimate (0.04 = 4% → ~8k verts) to remove fine details and strands
2. Close any holes (make manifold for solidify)
3. Laplacian smooth to unify surface (factor 0.10, 2 iters)
4. Solidify 1.5mm for 3D print wall
5. Toon material (cel-shaded 3-step)
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
# STEP 1: Strong decimate to remove fine details
# ------------------------------------------------------------------
print("\n=== STEP 1: Strong Decimate (keep 4% → ~8k verts) ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_dec = hair.modifiers.new("Decimate", "DECIMATE")
mod_dec.ratio = 0.04
mod_dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="Decimate")
hair.select_set(False)
print(f"  After decimate: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 2: Try to close holes (best-effort, skip if operator missing)
# ------------------------------------------------------------------
print("\n=== STEP 2: Fill holes (best-effort) ===")
bm = bmesh.new()
try:
    bm.from_mesh(hair.data)
    # Find boundary edges
    boundary_edges = [e for e in bm.edges if not e.is_manifold]
    print(f"  Found {len(boundary_edges)} boundary edges")
    # Try multiple fill operators
    if boundary_edges:
        filled = 0
        # Try edgenet_fill
        try:
            ret = bmesh.ops.edgenet_fill(bm, edges=boundary_edges, sides=4)
            filled = len(ret.get("faces", []))
            print(f"  edgenet_fill: {filled} new faces")
        except Exception as e:
            print(f"  edgenet_fill failed: {e}")
        # Try context-aware create
        try:
            ret = bmesh.ops.contextual_create(
                bm, geom=boundary_edges,
                use_interpolate=True,
            )
            filled = len(ret.get("faces", []))
            print(f"  contextual_create: {filled} new faces")
        except Exception as e:
            print(f"  contextual_create failed: {e}")
    # Remove isolated verts
    iso = [v for v in bm.verts if len(v.link_faces) == 0]
    if iso:
        bmesh.ops.dissolve_verts(bm, verts=iso)
        print(f"  Dissolved {len(iso)} isolated verts")
    bm.to_mesh(hair.data)
finally:
    bm.free()
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ------------------------------------------------------------------
# STEP 3: Laplacian smooth (factor 0.10, 3 iters = ~27% smooth)
# ------------------------------------------------------------------
print("\n=== STEP 3: Laplacian smoothing (3 iter factor 0.10) ===")
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
print(f"  After smooth: dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 4: Solidify 1.5mm for 3D print wall thickness
# ------------------------------------------------------------------
print("\n=== STEP 4: Solidify 1.5mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
mod_sol.use_even_offset = True
try:
    bpy.ops.object.modifier_apply(modifier="PrintSolidify")
    print(f"  Solidify applied: {len(hair.data.vertices)} verts, dims={hair.dimensions}")
except Exception as e:
    print(f"  Solidify failed: {e}")
hair.select_set(False)

# ------------------------------------------------------------------
# STEP 5: Toon material (3-step cel-shading)
# ------------------------------------------------------------------
print("\n=== STEP 5: Toon material ===")
hair.data.materials.clear()
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
elements[0].color = (0.40, 0.40, 0.45, 1.0)
elements[1].position = 0.50
elements[1].color = (0.78, 0.78, 0.82, 1.0)
hl = elements.new(0.85)
hl.color = (0.98, 0.98, 1.0, 1.0)
mat.node_tree.links.new(shader_to_rgb.outputs["Color"], color_ramp.inputs["Fac"])

emission = mat.node_tree.nodes.new("ShaderNodeEmission")
mat.node_tree.links.new(color_ramp.outputs["Color"], emission.inputs["Color"])
mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])

hair.data.materials.append(mat)
attrs = list(hair.data.color_attributes.keys())
for an in attrs:
    hair.data.color_attributes.remove(hair.data.color_attributes[an])
hair.data.color_attributes.render_color_index = -1
print("  Toon material: 3-step cel-shading")

# Save
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime_v4.blend"))
print(f"\nSaved hair_anime_v4.blend")

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
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_v4_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_v4_{view_name}.png")
