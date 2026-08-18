"""V7: Shrinkwrap a simple low-poly mesh onto the hair to get a clean unified shape.

Approach:
1. Decimate hair to get rough silhouette (0.10)
2. Create a UV sphere (low-poly) that fits the hair's bbox
3. Shrinkwrap the sphere to the hair
4. Solidify 1.5mm
5. Toon material
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
# STEP 1: Decimate hair (0.10) for a rough silhouette
# ------------------------------------------------------------------
print("\n=== STEP 1: Decimate hair (0.10) ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_dec = hair.modifiers.new("Decimate", "DECIMATE")
mod_dec.ratio = 0.10
mod_dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="Decimate")
hair.select_set(False)
print(f"  After decimate: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# Make hair a Smooth target (it's a closed mesh? probably not, but shrinkwrap will work)
# Smooth modifier to make hair surface smoother
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_smooth = hair.modifiers.new("PreSmooth", "SMOOTH")
mod_smooth.factor = 0.5
mod_smooth.iterations = 5
bpy.ops.object.modifier_apply(modifier="PreSmooth")
hair.select_set(False)
print(f"  After smooth: {len(hair.data.vertices)} verts, dims={hair.dimensions}")

# ------------------------------------------------------------------
# STEP 2: Create a low-poly mesh to shrinkwrap
# ------------------------------------------------------------------
print("\n=== STEP 2: Create low-poly UV sphere to shrinkwrap ===")
# Calculate hair center
bb = [hair.matrix_world @ Vector(c) for c in hair.bound_box]
center = sum(bb, Vector((0, 0, 0))) / 8.0
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3)
          for p in bb) if False else max(
              max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
print(f"  hair center: {center}, size: {size}")

# Use ELONGATED ellipsoid (since hair is elongated)
# Make a UV sphere with subdivisions=3 (low-poly)
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=size * 0.5,
    segments=12,
    ring_count=8,
    location=(center.x, center.y, center.z),
)
sphere = bpy.context.view_layer.objects.active
sphere.name = "AFR_ShrinkwrapMesh"
# Scale to match hair proportions
sphere.scale = (1.0, 0.7, 1.2)  # elongated like the hair
print(f"  Sphere created: v={len(sphere.data.vertices)}, dims={sphere.dimensions}")

# ------------------------------------------------------------------
# STEP 3: Shrinkwrap sphere to hair
# ------------------------------------------------------------------
print("\n=== STEP 3: Shrinkwrap sphere to hair ===")
bpy.context.view_layer.objects.active = sphere
sphere.select_set(True)
mod_sw = sphere.modifiers.new("Shrinkwrap", "SHRINKWRAP")
mod_sw.target = hair
mod_sw.wrap_method = 'PROJECT'  # project onto the target
mod_sw.project_limit = 0.5
mod_sw.use_negative_direction = True
mod_sw.use_positive_direction = True
mod_sw.cull_face = 'OFF'
try:
    bpy.ops.object.modifier_apply(modifier="Shrinkwrap")
    print(f"  Shrinkwrap done: v={len(sphere.data.vertices)}, dims={sphere.dimensions}")
except Exception as e:
    print(f"  Shrinkwrap failed: {e}")
sphere.select_set(False)

# ------------------------------------------------------------------
# STEP 4: Smooth the result
# ------------------------------------------------------------------
print("\n=== STEP 4: Smooth shrinkwrapped mesh ===")
bpy.context.view_layer.objects.active = sphere
sphere.select_set(True)
mod_smooth = sphere.modifiers.new("SmoothFinal", "SMOOTH")
mod_smooth.factor = 0.7
mod_smooth.iterations = 10
bpy.ops.object.modifier_apply(modifier="SmoothFinal")
sphere.select_set(False)
print(f"  After smooth: dims={sphere.dimensions}")

# ------------------------------------------------------------------
# STEP 5: Solidify
# ------------------------------------------------------------------
print("\n=== STEP 5: Solidify 1.5mm ===")
bpy.context.view_layer.objects.active = sphere
sphere.select_set(True)
mod_sol = sphere.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
try:
    bpy.ops.object.modifier_apply(modifier="PrintSolidify")
    print(f"  Solidify: v={len(sphere.data.vertices)}, dims={sphere.dimensions}")
except Exception as e:
    print(f"  Solidify failed: {e}")
sphere.select_set(False)

# Hide the original hair
hair.hide_render = True
hair.hide_viewport = True

# Rename sphere to be the new hair
sphere.name = "part_2.001"

# ------------------------------------------------------------------
# STEP 6: Toon material
# ------------------------------------------------------------------
print("\n=== STEP 6: Toon material ===")
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
elements[0].color = (0.40, 0.40, 0.45, 1.0)
elements[1].position = 0.50
elements[1].color = (0.78, 0.78, 0.82, 1.0)
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

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_anime_v7.blend"))
print(f"\nSaved hair_anime_v7.blend")

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
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"hair_v7_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved hair_v7_{view_name}.png")
