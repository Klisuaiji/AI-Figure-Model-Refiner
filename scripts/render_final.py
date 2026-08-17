"""Final clean render using intermediate_with_doll.blend + saved state.
- Loads intermediate_with_doll.blend
- Adds the right sun light
- Positions doll at main's center
- Adds decorations
- Renders clean BEFORE / AFTER comparison"""
import bpy
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\workflow_demo"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)

# Load original file
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

# Setup sun + world
bpy.context.scene.world.use_nodes = True
world_nodes = bpy.context.scene.world.node_tree.nodes
bg = world_nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.30, 0.30, 0.32, 1.0)
    bg.inputs["Strength"].default_value = 1.5
# Add a strong sun
light_data = bpy.data.lights.new("Sun2", type="SUN")
light_data.energy = 8.0
light_data.color = (1.0, 0.95, 0.85)
light_obj = bpy.data.objects.new("Sun2", light_data)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.location = (5, -5, 10)
# Add a fill light from the other side
light_data2 = bpy.data.lights.new("Fill2", type="SUN")
light_data2.energy = 2.0
light_obj2 = bpy.data.objects.new("Fill2", light_data2)
bpy.context.scene.collection.objects.link(light_obj2)
light_obj2.location = (-3, 3, 5)

# Setup EEVEE
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 1000
bpy.context.scene.render.resolution_y = 1000
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.context.scene.view_settings.view_transform = "Standard"


def frame_on(objs, view="diag", extra_dist=1.5):
    cam = bpy.context.scene.camera
    if cam is None:
        bpy.ops.object.camera_add()
        cam = bpy.context.view_layer.objects.active
        bpy.context.scene.camera = cam
    all_corners = []
    for o in objs:
        for c in o.bound_box:
            all_corners.append(o.matrix_world @ Vector(c))
    cx = sum(c.x for c in all_corners) / len(all_corners)
    cy = sum(c.y for c in all_corners) / len(all_corners)
    cz = sum(c.z for c in all_corners) / len(all_corners)
    center = Vector((cx, cy, cz))
    max_size = max(
        max(p[i] for p in all_corners) - min(p[i] for p in all_corners)
        for i in range(3)
    )
    dist = max_size * extra_dist
    if view == "front":
        cam.location = (center.x, center.y - dist, center.z + dist * 0.05)
    elif view == "back":
        cam.location = (center.x, center.y + dist, center.z + dist * 0.05)
    elif view == "left":
        cam.location = (center.x - dist, center.y, center.z + dist * 0.05)
    elif view == "right":
        cam.location = (center.x + dist, center.y, center.z + dist * 0.05)
    else:
        cam.location = (center.x + dist * 0.7, center.y - dist * 0.7, center.z + dist * 0.5)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()


# ------------------------------------------------------------------
# Render 1: BEFORE (original main, no labels)
# ------------------------------------------------------------------
print("=== Render BEFORE ===")
main_parts = [o for o in bpy.data.objects if o.name.startswith("part_")]
# Give main a uniform color (the original color attrs cause weird colors)
for p in main_parts:
    p.data.materials.clear()
    if p.name == "part_3.001":
        # Base — wooden color
        mat = bpy.data.materials.new(f"AFR_{p.name}")
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (0.42, 0.27, 0.14, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.6
        mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    else:
        # Body parts — soft fabric
        mat = bpy.data.materials.new(f"AFR_{p.name}")
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (0.80, 0.78, 0.75, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.7
        mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    p.data.materials.append(mat)
    # Clean color attributes
    attrs = list(p.data.color_attributes.keys())
    for an in attrs:
        p.data.color_attributes.remove(p.data.color_attributes[an])
    p.data.color_attributes.render_color_index = -1
# Hide everything except main parts
for o in bpy.data.objects:
    if o.name.startswith("part_"):
        o.hide_render = False
        o.hide_viewport = False
    else:
        o.hide_render = True
        o.hide_viewport = True
frame_on(main_parts, view="diag", extra_dist=1.6)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "FINAL_BEFORE_diag.png")
bpy.ops.render.render(write_still=True)
print("  saved FINAL_BEFORE_diag.png")
frame_on(main_parts, view="front", extra_dist=1.6)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "FINAL_BEFORE_front.png")
bpy.ops.render.render(write_still=True)
print("  saved FINAL_BEFORE_front.png")
frame_on(main_parts, view="back", extra_dist=1.6)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "FINAL_BEFORE_back.png")
bpy.ops.render.render(write_still=True)
print("  saved FINAL_BEFORE_back.png")

# ------------------------------------------------------------------
# Render 2: AFTER (doll + base + decorations)
# ------------------------------------------------------------------
print("\n=== Render AFTER ===")
# Hide all main parts
for o in bpy.data.objects:
    o.hide_render = True
    o.hide_viewport = True
# Load doll from intermediate_with_doll.blend
doll_data_path = os.path.join(OUT_DIR, "intermediate_with_doll.blend")
# Append doll
with bpy.data.libraries.load(doll_data_path, link=False) as (data_from, data_to):
    data_to.objects = [n for n in data_from.objects if n == "doll"]
for obj in data_to.objects:
    if obj is not None:
        bpy.context.scene.collection.objects.link(obj)
        obj.hide_render = False
        obj.hide_viewport = False
        # Re-clean materials (cross-blend refs may not load properly)
        for slot in list(obj.data.materials):
            obj.data.materials.clear()
        mat = bpy.data.materials.new("AFR_DollMat_Final")
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (0.92, 0.82, 0.68, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.85
        mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        obj.data.materials.append(mat)
        # Clean color attrs
        attrs = list(obj.data.color_attributes.keys())
        for an in attrs:
            obj.data.color_attributes.remove(obj.data.color_attributes[an])
        obj.data.color_attributes.render_color_index = -1
# Show base
base_part = bpy.data.objects.get("part_3.001")
if base_part:
    base_part.hide_render = False
    base_part.hide_viewport = False

# Show and position decorations
dec1 = bpy.data.objects.get("Mesh_0")
dec2 = bpy.data.objects.get("Mesh_0.001")
# Center
all_corners = []
for p in main_parts:
    for corner in p.bound_box:
        all_corners.append(p.matrix_world @ Vector(corner))
center_main = sum(all_corners, Vector((0, 0, 0))) / len(all_corners)
size_main = max(
    max(p[i] for p in all_corners) - min(p[i] for p in all_corners)
    for i in range(3)
)
if dec1:
    dec1.hide_render = False
    dec1.hide_viewport = False
    dec1.location = (center_main.x - size_main * 0.85, center_main.y - size_main * 0.4, center_main.z + size_main * 0.2)
    dec1.scale = (0.6, 1.0, 0.6)
    dec1.rotation_euler = (0, 0, 0.2)
    # Clean materials
    for slot in list(dec1.data.materials):
        dec1.data.materials.clear()
    mat = bpy.data.materials.new("AFR_Dec1_Final")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.85, 0.65, 0.30, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Metallic"].default_value = 0.7
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    dec1.data.materials.append(mat)
    attrs = list(dec1.data.color_attributes.keys())
    for an in attrs:
        dec1.data.color_attributes.remove(dec1.data.color_attributes[an])
    dec1.data.color_attributes.render_color_index = -1
if dec2:
    dec2.hide_render = False
    dec2.hide_viewport = False
    dec2.location = (center_main.x + size_main * 0.9, center_main.y + size_main * 0.2, center_main.z + size_main * 0.1)
    dec2.scale = (0.5, 0.5, 0.5)
    for slot in list(dec2.data.materials):
        dec2.data.materials.clear()
    mat = bpy.data.materials.new("AFR_Dec2_Final")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.20, 0.45, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    dec2.data.materials.append(mat)
    attrs = list(dec2.data.color_attributes.keys())
    for an in attrs:
        dec2.data.color_attributes.remove(dec2.data.color_attributes[an])
    dec2.data.color_attributes.render_color_index = -1

# Position doll sitting on the base
doll = bpy.data.objects.get("doll")
base_part = bpy.data.objects.get("part_3.001")
if doll and base_part:
    # Reset doll location to identity first to get its pure bbox
    doll.location = (0, 0, 0)
    bpy.context.view_layer.update()
    # Get doll's bbox in local (which equals world since location is 0)
    doll_min_z_local = min((Vector(c)).z for c in doll.bound_box)
    # Get base's top
    base_top_z = max((base_part.matrix_world @ Vector(c)).z for c in base_part.bound_box)
    # Set doll position so its bottom sits on the base top
    doll.location = (center_main.x, center_main.y, base_top_z - doll_min_z_local)
    bpy.context.view_layer.update()
    doll.hide_render = False
    doll.hide_viewport = False
    print(f"  doll bbox local min_z = {doll_min_z_local:.3f}")
    print(f"  base top z = {base_top_z:.3f}")
    print(f"  doll location = {doll.location}")
    # Verify
    actual_min_z = min((doll.matrix_world @ Vector(c)).z for c in doll.bound_box)
    print(f"  actual doll world min_z = {actual_min_z:.3f} (should equal base_top_z)")

# Render AFTER
visible = [o for o in bpy.data.objects if not o.hide_render and o.type == "MESH"]
print(f"  visible: {[o.name for o in visible]}")
frame_on(visible, view="diag", extra_dist=1.6)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "FINAL_AFTER_diag.png")
bpy.ops.render.render(write_still=True)
print("  saved FINAL_AFTER_diag.png")
frame_on(visible, view="front", extra_dist=1.6)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "FINAL_AFTER_front.png")
bpy.ops.render.render(write_still=True)
print("  saved FINAL_AFTER_front.png")
frame_on(visible, view="back", extra_dist=1.6)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "FINAL_AFTER_back.png")
bpy.ops.render.render(write_still=True)
print("  saved FINAL_AFTER_back.png")

# Save final blend
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "FINAL_substituted.blend"))
print("  saved FINAL_substituted.blend")
