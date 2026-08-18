"""V0.8 workflow demo v2 - fixed doll generation using Decimate modifier."""
import bpy
import os
import sys
import json
import bmesh
from mathutils import Vector
import random

ADDON_PARENT = r"D:\Qq203/Downloads/AI Figure Model Refiner\addon"
if ADDON_PARENT not in sys.path:
    sys.path.append(ADDON_PARENT)

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\workflow_demo"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

import ai_figure_refiner
ai_figure_refiner.register()
from ai_figure_refiner.semantic.parts import (
    PART_LABELS, PART_ID, ID_PART, PART_COLORS,
    ensure_part_attribute, get_label_array, set_label_array,
    set_vertex_color_overlay, apply_heuristics, brush_flood,
    brush_apply,
)
from ai_figure_refiner.parts_ops.hair import extract_part


# ------------------------------------------------------------------
# Setup render env (BEFORE step 1)
# ------------------------------------------------------------------
def setup_render():
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.eevee.taa_render_samples = 32
    bpy.context.scene.render.resolution_x = 800
    bpy.context.scene.render.resolution_y = 800
    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.render.image_settings.color_mode = "RGBA"
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.view_settings.view_transform = "Standard"


def setup_label_material(obj):
    """Set the object's active material to show vertex colors (so labels are visible)."""
    mat = bpy.data.materials.new("AFR_LabelViz")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    # Add vertex color node
    vc = nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "AFR_PartColor"
    # Connect color to base color
    mat.node_tree.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    # Set up transparency for uncolored areas
    bsdf.inputs["Alpha"].default_value = 1.0
    mat.blend_method = "OPAQUE"
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    obj.active_material = mat
    # Set the AFR_PartColor as the render color attribute
    if "AFR_PartColor" in obj.data.color_attributes:
        obj.data.color_attributes.render_color_index = (
            obj.data.color_attributes.find("AFR_PartColor"))


def render_png(filename, only_objs=None, view="diag", exclude_objs=None):
    """Render PNG. If only_objs given, only those names are shown (rest hidden via collection)."""
    # Use collection-level hiding which is reliable in background mode
    if only_objs is not None or exclude_objs is not None:
        for o in bpy.data.objects:
            if only_objs is not None:
                hide = (o.name not in only_objs)
            else:
                hide = (o.name in exclude_objs)
            o.hide_render = hide
            o.hide_viewport = hide
    else:
        for o in bpy.data.objects:
            o.hide_render = False
            o.hide_viewport = False
    if bpy.context.scene.camera is None:
        bpy.context.scene.camera = bpy.data.objects.get("Camera")
    cam = bpy.context.scene.camera
    visible = [o for o in bpy.data.objects if not o.hide_render and o.type == "MESH"]
    if not visible:
        return
    all_corners = []
    for o in visible:
        for corner in o.bound_box:
            all_corners.append(o.matrix_world @ Vector(corner))
    cx = sum(c.x for c in all_corners) / len(all_corners)
    cy = sum(c.y for c in all_corners) / len(all_corners)
    cz = sum(c.z for c in all_corners) / len(all_corners)
    center = Vector((cx, cy, cz))
    max_size = max(
        max(p[i] for p in all_corners) - min(p[i] for p in all_corners)
        for i in range(3)
    )
    if view == "front":
        cam.location = (center.x, center.y - max_size * 1.6, center.z + max_size * 0.1)
    elif view == "back":
        cam.location = (center.x, center.y + max_size * 1.6, center.z + max_size * 0.1)
    else:
        cam.location = (center.x + max_size * 1.0, center.y - max_size * 1.0, center.z + max_size * 0.7)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, filename)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)


setup_render()

# ------------------------------------------------------------------
# STEP 0: identify main parts
# ------------------------------------------------------------------
print("=== STEP 0: identify main cluster ===")
main_parts = [o for o in bpy.data.objects if o.name.startswith("part_")]
print(f"  main cluster: {len(main_parts)} parts")

# Render original (BEFORE) for comparison
print("\n=== Render: 00_BEFORE (original main only) ===")
for o in bpy.data.objects:
    if o.name.startswith("part_"):
        o.hide_render = False
        o.hide_viewport = False
    else:
        o.hide_render = True
        o.hide_viewport = True
render_png("00_BEFORE_main_only_front.png", view="front", only_objs={p.name for p in main_parts})
render_png("00_BEFORE_main_only_diag.png", view="diag", only_objs={p.name for p in main_parts})
# Reset visibility
for o in bpy.data.objects:
    o.hide_render = False
    o.hide_viewport = False
render_png("00_BEFORE_main_only_diag.png", view="diag", only_objs={p.name for p in main_parts})
# ------------------------------------------------------------------
print("=== STEP 0: identify main cluster ===")
main_parts = [o for o in bpy.data.objects if o.name.startswith("part_")]
print(f"  main cluster: {len(main_parts)} parts")

# ------------------------------------------------------------------
# STEP 1: Apply semantic labels to each part
# ------------------------------------------------------------------
print("\n=== STEP 1: apply semantic labels to each part ===")
label_summary = {}
for p in main_parts:
    bpy.context.view_layer.objects.active = p
    labels = apply_heuristics(p)
    setup_label_material(p)
    counts = {n: 0 for n in PART_LABELS}
    for lab in labels:
        counts[ID_PART[lab]] += 1
    label_summary[p.name] = counts
    print(f"  {p.name}: {dict((k, v) for k, v in counts.items() if v)}")

# Render with label colors visible
print("\n=== Render: 01_main_with_labels ===")
render_png("01_main_with_labels_front.png", view="front")
render_png("01_main_with_labels_diag.png", view="diag")

# ------------------------------------------------------------------
# STEP 2: Extract HAIR / FABRIC / BASE / BODY / HEAD from main
# ------------------------------------------------------------------
print("\n=== STEP 2: extract parts ===")
extracted = {}
for part_name, label_name in [("hair", "HAIR"), ("fabric", "FABRIC"),
                              ("base", "BASE"), ("body", "BODY"),
                              ("head", "HEAD")]:
    best_name = max(label_summary.items(),
                    key=lambda kv: kv[1].get(label_name, 0))[0]
    src = bpy.data.objects[best_name]
    obj = extract_part(src, PART_ID[label_name], new_name=f"{part_name}_extracted")
    if obj is not None:
        setup_label_material(obj)
        extracted[part_name] = obj
    print(f"  {part_name}: source={best_name}, verts={len(obj.data.vertices) if obj else 0}")

# Render split result
print("\n=== Render: 02_main_split ===")
# Make sure extracted are visible, originals hidden (to see only extracted)
for p in main_parts:
    p.hide_render = True
    p.hide_viewport = True
for o in extracted.values():
    o.hide_render = False
    o.hide_viewport = False
render_png("02_extracted_parts_diag.png", view="diag")
render_png("02_extracted_parts_front.png", view="front")

# Restore for next steps
for p in main_parts:
    p.hide_render = False
    p.hide_viewport = False

# ------------------------------------------------------------------
# STEP 3: Generate DOLL from main (clone all parts, decimate, merge, flatten)
# ------------------------------------------------------------------
print("\n=== STEP 3: generate DOLL ===")

# Calculate main's combined bbox
all_corners = []
for p in main_parts:
    for corner in p.bound_box:
        all_corners.append(p.matrix_world @ Vector(corner))
center_main = sum(all_corners, Vector((0, 0, 0))) / len(all_corners)
size_main = max(
    max(p[i] for p in all_corners) - min(p[i] for p in all_corners)
    for i in range(3)
)
print(f"  main center: {center_main}, size: {size_main:.2f}")

# Strategy: clone each main part, then DECIMATE modifier (which exists
# in 5.2 — only the bmesh.ops variant is missing). Then join, then flatten.
doll_clones = []
for p in main_parts:
    # Duplicate the object
    new_obj = p.copy()
    if p.data:
        new_obj.data = p.data.copy()
    new_obj.name = f"{p.name}_doll_clone"
    bpy.context.scene.collection.objects.link(new_obj)
    # Clear label materials so the clone doesn't render with vertex colors
    new_obj.data.materials.clear()
    # Add decimate modifier
    mod = new_obj.modifiers.new("Decimate", "DECIMATE")
    mod.ratio = 0.15  # keep 15%
    mod.use_collapse_triangulate = True
    # Apply modifier
    bpy.context.view_layer.objects.active = new_obj
    new_obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier="Decimate")
    doll_clones.append(new_obj)
    print(f"  cloned {p.name}: {len(new_obj.data.vertices)} verts (was {len(p.data.vertices)})")

# Join all doll clones into one mesh
bpy.ops.object.select_all(action="DESELECT")
for d in doll_clones:
    d.select_set(True)
bpy.context.view_layer.objects.active = doll_clones[0]
bpy.ops.object.join()
doll = bpy.context.view_layer.objects.active
doll.name = "doll"

# Apply scale to flatten on Z (cloth-doll pillow)
doll.scale = (1.0, 1.0, 0.6)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Apply solidify to make it pillow-like
mod = doll.modifiers.new("DollSolidify", "SOLIDIFY")
mod.thickness = 0.005
mod.offset = -1.0
bpy.context.view_layer.objects.active = doll
bpy.ops.object.modifier_apply(modifier="DollSolidify")

# Smooth shading
bpy.ops.object.shade_smooth()

# Material for doll (cloth-doll beige — like a stuffed fabric doll)
mat = bpy.data.materials.new("AFR_DollMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.92, 0.82, 0.68, 1.0)  # warm cloth
bsdf.inputs["Roughness"].default_value = 0.85
# Add a solid color input to ENSURE no vertex color leakage
# Clear ALL inputs that might be coming from vertex color
mat.node_tree.nodes.clear()
output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
principled = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
principled.inputs["Base Color"].default_value = (0.92, 0.82, 0.68, 1.0)
principled.inputs["Roughness"].default_value = 0.85
mat.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
# Clear existing material slots and assign only the new one
doll.data.materials.clear()
doll.data.materials.append(mat)
# Remove ALL color attributes so labels / original part colors don't show
attrs_to_remove = list(doll.data.color_attributes.keys())
for attr_name in attrs_to_remove:
    if attr_name in doll.data.color_attributes:
        doll.data.color_attributes.remove(doll.data.color_attributes[attr_name])
# -1 means "no color attribute used" — pure material color
doll.data.color_attributes.render_color_index = -1

print(f"  doll final: {len(doll.data.vertices)} verts, "
      f"dims={doll.dimensions}")

# Save intermediate
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "intermediate_with_doll.blend"))

# Render doll alone
print("\n=== Render: 03_doll_only ===")
for o in bpy.data.objects:
    hide = (o.name != "doll")
    o.hide_render = hide
    o.hide_viewport = hide
render_png("03_doll_only_diag.png", view="diag")
render_png("03_doll_only_front.png", view="front")
render_png("03_doll_only_back.png", view="back")

# ------------------------------------------------------------------
# STEP 4: Substitute main's person with doll, bring in decorations
# ------------------------------------------------------------------
print("\n=== STEP 4: substitute doll + bring in decorations ===")
# Hide the original main parts (the 'person' content of main)
for p in main_parts:
    p.hide_render = True
    p.hide_viewport = True
# Hide extracted parts (they were intermediate; the doll replaces the person)
for o in extracted.values():
    o.hide_render = True
    o.hide_viewport = True
# Show base (the pedestal) from main
base_part = bpy.data.objects.get("part_3.001")
if base_part:
    base_part.hide_render = False
    base_part.hide_viewport = False
    # Give base a nice wood color
    if not base_part.data.materials or "AFR_Base" not in [m.name for m in base_part.data.materials]:
        base_part.data.materials.clear()
        mat = bpy.data.materials.new("AFR_Base")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.42, 0.27, 0.14, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.6
        base_part.data.materials.append(mat)
        # Remove color attributes that might override
        attrs = list(base_part.data.color_attributes.keys())
        for an in attrs:
            base_part.data.color_attributes.remove(base_part.data.color_attributes[an])
        base_part.data.color_attributes.render_color_index = -1
# Show doll
doll.hide_render = False
doll.hide_viewport = False
# Position doll at main's center
doll.location = center_main

# Bring in decoration1 (Mesh_0) and decoration2 (Mesh_0.001)
dec1 = bpy.data.objects.get("Mesh_0")
dec2 = bpy.data.objects.get("Mesh_0.001")
# Position decorations around the doll (smaller than main, clear positions)
if dec1:
    dec1.hide_render = False
    dec1.hide_viewport = False
    # To the LEFT-front of the doll (a flat lyre ornament, tilted slightly)
    dec1.location = (center_main.x - size_main * 0.85, center_main.y - size_main * 0.4, center_main.z + size_main * 0.2)
    dec1.scale = (0.6, 1.0, 0.6)
    dec1.rotation_euler = (0, 0, 0.2)  # slight tilt
    dec1.data.materials.clear()
    mat = bpy.data.materials.new("AFR_Dec1")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out_n = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf_n = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_n.inputs["Base Color"].default_value = (0.78, 0.55, 0.20, 1.0)  # golden lyre
    bsdf_n.inputs["Roughness"].default_value = 0.4
    bsdf_n.inputs["Metallic"].default_value = 0.7
    mat.node_tree.links.new(bsdf_n.outputs["BSDF"], out_n.inputs["Surface"])
    dec1.data.materials.append(mat)
    # Clean color attrs
    attrs = list(dec1.data.color_attributes.keys())
    for an in attrs:
        dec1.data.color_attributes.remove(dec1.data.color_attributes[an])
    dec1.data.color_attributes.render_color_index = -1
    print(f"  decoration1 at {dec1.location}, dims={dec1.dimensions}")
if dec2:
    dec2.hide_render = False
    dec2.hide_viewport = False
    # To the RIGHT-back of the doll (long 3D strip, like a backdrop piece)
    dec2.location = (center_main.x + size_main * 0.9, center_main.y + size_main * 0.2, center_main.z + size_main * 0.1)
    dec2.scale = (0.5, 0.5, 0.5)
    dec2.data.materials.clear()
    mat = bpy.data.materials.new("AFR_Dec2")
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.20, 0.45, 1.0)  # purple
    bsdf.inputs["Roughness"].default_value = 0.6
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    dec2.data.materials.append(mat)
    # Clean color attrs
    attrs = list(dec2.data.color_attributes.keys())
    for an in attrs:
        dec2.data.color_attributes.remove(dec2.data.color_attributes[an])
    dec2.data.color_attributes.render_color_index = -1
    print(f"  decoration2 at {dec2.location}, dims={dec2.dimensions}")

# Final render
print("\n=== Render: 05_final ===")
render_png("05_final_diag.png", view="diag")
render_png("05_final_front.png", view="front")
render_png("05_final_back.png", view="back")

# Save final
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "final.blend"))

print("\n=== SUMMARY ===")
print(f"  main parts: {len(main_parts)} (original)")
print(f"  extracted: {list(extracted.keys())}")
print(f"  doll: {doll.name} ({len(doll.data.vertices)} verts, dims={doll.dimensions})")
print(f"  decoration1: Mesh_0 ({dec1.dimensions if dec1 else 'missing'})")
print(f"  decoration2: Mesh_0.001 ({dec2.dimensions if dec2 else 'missing'})")
print(f"  final: {OUT_DIR}/final.blend")
