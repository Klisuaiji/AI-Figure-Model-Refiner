"""Render original part_2.001 (the hair) standalone to confirm."""
import bpy
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"

# Add sun light
if "Sun" not in bpy.data.objects:
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 4.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)

bpy.context.scene.world.use_nodes = True
bgn = bpy.context.scene.world.node_tree.nodes.get("Background")
if bgn:
    bgn.inputs["Color"].default_value = (0.4, 0.4, 0.42, 1.0)
    bgn.inputs["Strength"].default_value = 0.6


def frame_on(objs, view="diag", extra=1.5):
    cam = bpy.context.scene.camera
    if cam is None or cam.name == "Camera":
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
    dist = max_size * extra
    if view == "front":
        cam.location = (center.x, center.y - dist, center.z + dist * 0.05)
    elif view == "back":
        cam.location = (center.x, center.y + dist, center.z + dist * 0.05)
    elif view == "side":
        cam.location = (center.x + dist, center.y, center.z + dist * 0.05)
    else:
        cam.location = (center.x + dist * 0.7, center.y - dist * 0.7, center.z + dist * 0.5)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()


def setup_anime_material(obj, base_color, name):
    """Set up a smooth anime-style material."""
    obj.data.materials.clear()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.append(mat)
    # Remove vertex color overrides
    attrs = list(obj.data.color_attributes.keys())
    for an in attrs:
        obj.data.color_attributes.remove(obj.data.color_attributes[an])
    obj.data.color_attributes.render_color_index = -1


# ------------------------------------------------------------------
# STEP 1: Hide everything, show only part_2.001 (the hair)
# ------------------------------------------------------------------
print("=== STEP 1: render HAIR (part_2.001) BEFORE ===")
hair = bpy.data.objects.get("part_2.001")
for o in bpy.data.objects:
    o.hide_render = (o is not hair)
    o.hide_viewport = (o is not hair)
setup_anime_material(hair, (0.85, 0.85, 0.90, 1.0), "AFR_HairMat")
frame_on([hair], view="diag", extra=1.8)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "01_HAIR_BEFORE_diag.png")
bpy.ops.render.render(write_still=True)
print("  saved 01_HAIR_BEFORE_diag.png")
frame_on([hair], view="side", extra=1.8)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "01_HAIR_BEFORE_side.png")
bpy.ops.render.render(write_still=True)
print("  saved 01_HAIR_BEFORE_side.png")
