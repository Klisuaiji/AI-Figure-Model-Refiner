"""V5: Connected-components filter to remove spaghetti strands.

Steps:
1. Decimate to reduce density (0.08 → 15k)
2. Find connected components, keep only the largest
3. Fill holes in the remaining component
4. Smooth + Solidify + Toon
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
# STEP 1: Moderate decimate
# ------------------------------------------------------------------
print("\n=== STEP 1: Decimate 0.08 (~15k verts) ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_dec = hair.modifiers.new("Decimate", "DECIMATE")
mod_dec.ratio = 0.08
mod_dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="Decimate")
hair.select_set(False)
print(f"  After decimate: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 2: Find connected components, keep only the largest
# ------------------------------------------------------------------
print("\n=== STEP 2: Connected components filter (keep top 3) ===")
bm = bmesh.new()
try:
    bm.from_mesh(hair.data)
    # Find connected components (each connected island of geometry)
    components = bmesh.ops.split(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], use_only_faces=True)
    # Actually, the right approach: find faces reachable from each face
    # Simpler: use bmesh.calc_loop_triangles? No.
    # Best: iterate through faces, group by connectivity
    # Or: use bmesh's "calc_stats" or directly check shared edges
    # Manual approach: flood-fill from each unvisited face
    all_faces = list(bm.faces)
    visited = set()
    islands = []
    face_to_island = {}
    for f in all_faces:
        if f in visited:
            continue
        # BFS
        island_faces = set()
        queue = [f]
        while queue:
            cf = queue.pop(0)
            if cf in visited:
                continue
            visited.add(cf)
            island_faces.add(cf)
            face_to_island[cf] = len(islands)
            for edge in cf.edges:
                for nf in edge.link_faces:
                    if nf not in visited:
                        queue.append(nf)
        islands.append(island_faces)
    print(f"  Found {len(islands)} connected components")
    # Sort by number of faces, descending
    islands.sort(key=lambda s: -len(s))
    # Keep top 3 islands
    keep_islands = islands[:3]
    keep_faces = set()
    for i in keep_islands:
        keep_faces |= i
    # Delete faces not in keep set
    to_delete = [f for f in all_faces if f not in keep_faces]
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context="FACES")
    # Delete orphaned verts/edges
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(hair.data)
finally:
    bm.free()
hair.data.update()
print(f"  After component filter: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 3: Fill remaining holes
# ------------------------------------------------------------------
print("\n=== STEP 3: Fill remaining holes ===")
bm = bmesh.new()
try:
    bm.from_mesh(hair.data)
    boundary = [e for e in bm.edges if not e.is_manifold]
    print(f"  {len(boundary)} boundary edges")
    if boundary:
        try:
            ret = bmesh.ops.edgenet_fill(bm, edges=boundary[:200], sides=4)
            print(f"  Filled {len(ret.get('faces', []))} faces")
        except Exception as e:
            print(f"  Fill failed: {e}")
    bm.to_mesh(hair.data)
finally:
    bm.free()
hair.data.update()

# ------------------------------------------------------------------
# STEP 4: Laplacian smooth (3 iter factor 0.10)
# ------------------------------------------------------------------
print("\n=== STEP 4: Laplacian smoothing (3 iter factor 0.10) ===")
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
# STEP 5: Solidify 1.5mm
# ------------------------------------------------------------------
print("\n=== STEP 5: Solidify 1.5mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
try:
    bpy.ops.object.modifier_apply(modifier="PrintSolidify")
    print(f"  Solidify: {len(hair.data.vertices)} verts, dims={hair.dimensions}")
except Exception as e:
    print(f"  Solidify failed: {e}")
hair.select_set(False)

# ------------------------------------------------------------------
# STEP 6: Toon material
# ------------------------------------------------------------------
print("\n=== STEP 6: Toon material ===")
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
print("  Toon: 3-step cel-shading")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime_v5.blend"))
print(f"\nSaved hair_anime_v5.blend")

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
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_v5_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_v5_{view_name}.png")
