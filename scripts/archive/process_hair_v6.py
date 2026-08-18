"""V6: Use Blender's Separate by Loose Parts to remove spaghetti.

Steps:
1. Decimate moderately
2. Edit mode → Select All → Separate by Loose Parts
3. Out of context, delete small parts
4. Join remaining
5. Smooth + Solidify + Toon
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
# STEP 1: Decimate moderately
# ------------------------------------------------------------------
print("\n=== STEP 1: Decimate 0.10 (~19k verts) ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_dec = hair.modifiers.new("Decimate", "DECIMATE")
mod_dec.ratio = 0.10
mod_dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="Decimate")
hair.select_set(False)
print(f"  After decimate: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 2: Separate by Loose Parts
# ------------------------------------------------------------------
print("\n=== STEP 2: Separate by Loose Parts ===")
bpy.context.view_layer.objects.active = hair
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.separate(type='LOOSE')
bpy.ops.object.mode_set(mode='OBJECT')

# Now we have multiple objects (one per loose part)
all_objs = [o for o in bpy.data.objects if o.type == "MESH"]
print(f"  After separate: {len(all_objs)} mesh objects")
for o in all_objs:
    print(f"    {o.name}: v={len(o.data.vertices)}")

# Sort by vert count, keep top 3
all_objs.sort(key=lambda o: -len(o.data.vertices))
print(f"\n  Top 3 by vertex count:")
for o in all_objs[:3]:
    print(f"    {o.name}: v={len(o.data.vertices)}")
# Keep only top 3, delete the rest
to_delete = all_objs[3:]
for o in to_delete:
    bpy.data.objects.remove(o, do_unlink=True)
print(f"  Deleted {len(to_delete)} small loose parts")

# ------------------------------------------------------------------
# STEP 3: Join the remaining objects
# ------------------------------------------------------------------
print("\n=== STEP 3: Join remaining parts ===")
bpy.context.view_layer.objects.active = all_objs[0]
bpy.ops.object.select_all(action='DESELECT')
for o in all_objs[:3]:
    o.select_set(True)
bpy.context.view_layer.objects.active = all_objs[0]
bpy.ops.object.join()
hair = bpy.context.view_layer.objects.active
hair.name = "part_2.001"
print(f"  Joined: {hair.name}: v={len(hair.data.vertices)}, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 4: Fill holes
# ------------------------------------------------------------------
print("\n=== STEP 4: Fill holes ===")
bpy.context.view_layer.objects.active = hair
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.fill_holes(sides=200)
bpy.ops.object.mode_set(mode='OBJECT')
print(f"  After fill: v={len(hair.data.vertices)}, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 5: Smooth (3 iter factor 0.10)
# ------------------------------------------------------------------
print("\n=== STEP 5: Smooth (3 iter factor 0.10) ===")
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
# STEP 6: Solidify 1.5mm
# ------------------------------------------------------------------
print("\n=== STEP 6: Solidify 1.5mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
try:
    bpy.ops.object.modifier_apply(modifier="PrintSolidify")
    print(f"  Solidify: v={len(hair.data.vertices)}, dims={hair.dimensions}")
except Exception as e:
    print(f"  Solidify failed: {e}")
hair.select_set(False)

# ------------------------------------------------------------------
# STEP 7: Toon material
# ------------------------------------------------------------------
print("\n=== STEP 7: Toon material ===")
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

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime_v6.blend"))
print(f"\nSaved hair_anime_v6.blend")

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
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_v6_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_v6_{view_name}.png")
