"""V0.8 demo workflow: 
1) Apply semantic labels to all part_X.001 (main figure parts)
2) Split into HAIR / FABRIC / BASE / BODY / HEAD sub-objects
3) Generate DOLL from main (merged + decimated + slightly flattened)
4) Replace main's person with the doll, scaled to match
5) Bring in decoration1 (Mesh_0) and decoration2 (Mesh_0.001)
6) Save result + render before/after
"""
import bpy
import os
import sys
import json
import bmesh
from mathutils import Vector

ADDON_PARENT = r"D:\Qq203\Downloads\AI Figure Model Refiner\addon"
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
from ai_figure_refiner.parts_ops.voronoi import voronoi_lattice


def render_png(filename, only_objs=None, view="diag"):
    """Render the scene. If only_objs is given, hide all others."""
    if only_objs is not None:
        for o in bpy.data.objects:
            o.hide_render = (o.name not in only_objs)
    else:
        for o in bpy.data.objects:
            o.hide_render = False
    # Ensure camera + light
    if bpy.context.scene.camera is None:
        bpy.context.scene.camera = bpy.data.objects.get("Camera")
    cam = bpy.context.scene.camera
    # Frame on visible
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
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.eevee.taa_render_samples = 32
    bpy.context.scene.render.resolution_x = 800
    bpy.context.scene.render.resolution_y = 800
    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.render.image_settings.color_mode = "RGBA"
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.view_settings.view_transform = "Standard"
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------
# STEP 0: Tag collections (visual, not Blender collections)
# ------------------------------------------------------------------
print("=== STEP 0: identify roles ===")
main_parts = [o for o in bpy.data.objects if o.name.startswith("part_")]
print(f"  main cluster: {len(main_parts)} parts")
for p in main_parts:
    print(f"    {p.name}: {len(p.data.vertices)} verts")

# ------------------------------------------------------------------
# STEP 1: Apply semantic labels to every part of main
# ------------------------------------------------------------------
print("\n=== STEP 1: apply semantic labels to each part_X.001 ===")
label_summary = {}
for p in main_parts:
    bpy.context.view_layer.objects.active = p
    labels = apply_heuristics(p)
    counts = {n: 0 for n in PART_LABELS}
    for lab in labels:
        counts[ID_PART[lab]] += 1
    label_summary[p.name] = counts
    print(f"  {p.name}: {dict((k, v) for k, v in counts.items() if v)}")

# ------------------------------------------------------------------
# STEP 2: Render BEFORE (with color overlay so labels are visible)
# ------------------------------------------------------------------
print("\n=== STEP 2: render BEFORE ===")
render_png("01_main_with_labels_front.png", view="front")
render_png("01_main_with_labels_back.png", view="back")
render_png("01_main_with_labels_diag.png", view="diag")

# ------------------------------------------------------------------
# STEP 3: Extract HAIR part from main → 'hair_extracted' object
#         (Use the part with most HAIR labels, which is part_2.001)
# ------------------------------------------------------------------
print("\n=== STEP 3: extract HAIR ===")
# Find the part with most HAIR verts
best_hair = max(label_summary.items(), key=lambda kv: kv[1].get("HAIR", 0))
print(f"  best hair source: {best_hair[0]} (HAIR={best_hair[1].get('HAIR', 0)})")
hair_src = bpy.data.objects[best_hair[0]]
hair_obj = extract_part(hair_src, PART_ID["HAIR"], new_name="hair_extracted")
print(f"  extracted: {hair_obj.name if hair_obj else 'FAILED'}")

# ------------------------------------------------------------------
# STEP 4: Extract FABRIC from main
# ------------------------------------------------------------------
print("\n=== STEP 4: extract FABRIC ===")
# FABRIC lives mostly on part_7 (red mantle) + part_8 (white dress)
# Pick the part with most FABRIC verts
best_fabric = max(label_summary.items(), key=lambda kv: kv[1].get("FABRIC", 0))
print(f"  best fabric source: {best_fabric[0]} (FABRIC={best_fabric[1].get('FABRIC', 0)})")
fabric_src = bpy.data.objects[best_fabric[0]]
fabric_obj = extract_part(fabric_src, PART_ID["FABRIC"], new_name="fabric_extracted")
print(f"  extracted: {fabric_obj.name if fabric_obj else 'FAILED'}")

# ------------------------------------------------------------------
# STEP 5: Extract BASE (pedestal)
# ------------------------------------------------------------------
print("\n=== STEP 5: extract BASE ===")
best_base = max(label_summary.items(), key=lambda kv: kv[1].get("BASE", 0))
print(f"  best base source: {best_base[0]} (BASE={best_base[1].get('BASE', 0)})")
base_src = bpy.data.objects[best_base[0]]
base_obj = extract_part(base_src, PART_ID["BASE"], new_name="base_extracted")
print(f"  extracted: {base_obj.name if base_obj else 'FAILED'}")

# ------------------------------------------------------------------
# STEP 6: Extract BODY + HEAD
# ------------------------------------------------------------------
print("\n=== STEP 6: extract BODY + HEAD ===")
best_body = max(label_summary.items(), key=lambda kv: kv[1].get("BODY", 0))
print(f"  best body source: {best_body[0]} (BODY={best_body[1].get('BODY', 0)})")
body_src = bpy.data.objects[best_body[0]]
body_obj = extract_part(body_src, PART_ID["BODY"], new_name="body_extracted")
print(f"  extracted: {body_obj.name if body_obj else 'FAILED'}")
best_head = max(label_summary.items(), key=lambda kv: kv[1].get("HEAD", 0))
print(f"  best head source: {best_head[0]} (HEAD={best_head[1].get('HEAD', 0)})")
head_src = bpy.data.objects[best_head[0]]
head_obj = extract_part(head_src, PART_ID["HEAD"], new_name="head_extracted")
print(f"  extracted: {head_obj.name if head_obj else 'FAILED'}")

# Save intermediate
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "intermediate_after_split.blend"))
print(f"  saved: intermediate_after_split.blend")

# ------------------------------------------------------------------
# STEP 7: Render AFTER-SPLIT (color-coded parts)
# ------------------------------------------------------------------
print("\n=== STEP 7: render after-split (parts visible) ===")
render_png("02_main_split_diag.png", view="diag")
render_png("02_main_split_front.png", view="front")
render_png("02_main_split_back.png", view="back")

# ------------------------------------------------------------------
# STEP 8: Generate DOLL from main (merge + decimate + flatten)
# ------------------------------------------------------------------
print("\n=== STEP 8: generate DOLL ===")

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
print(f"  main center: {center_main}, size: {size_main}")

# Duplicate main parts (bmesh) and merge into a single doll
doll_parts = []
for p in main_parts:
    bm = bmesh.new()
    try:
        bm.from_mesh(p.data)
        bm.transform(p.matrix_world)
        # Reduce to ~5% via decimate
        ratio = 0.05
        bm.verts.ensure_lookup_table()
        # Random decimation (manual for simplicity)
        import random
        rng = random.Random(0)
        keep_prob = ratio
        del_verts = [v for v in bm.verts if rng.random() > keep_prob]
        bmesh.ops.delete(bm, geom=del_verts, context="VERTS")
        # Decimate
        try:
            bmesh.ops.decimate(bm, ratio=ratio, use_collapse_triangle=True)
        except Exception as e:
            print(f"  decimate failed for {p.name}: {e}")
        # Slight flatten on Z to make it pillow-like
        for v in bm.verts:
            v.co.z = v.co.z * 0.6 + center_main.z * 0.4
        new_me = bpy.data.meshes.new(f"{p.name}_doll_me")
        bm.to_mesh(new_me)
        bm.free()
        new_obj = bpy.data.objects.new(f"{p.name}_doll", new_me)
        bpy.context.scene.collection.objects.link(new_obj)
        doll_parts.append(new_obj)
    except Exception as e:
        bm.free()
        print(f"  Dollify {p.name} failed: {e}")

# Join all doll parts into one
bpy.ops.object.select_all(action="DESELECT")
for d in doll_parts:
    d.select_set(True)
bpy.context.view_layer.objects.active = doll_parts[0]
bpy.ops.object.join()
doll = bpy.context.view_layer.objects.active
doll.name = "doll"

# Apply solidify to make it pillow-like
mod = doll.modifiers.new("DollSolidify", "SOLIDIFY")
mod.thickness = 0.005
mod.offset = 0.0
bpy.ops.object.modifier_apply(modifier="DollSolidify")

# Apply slight scale to flatten on Z (cloth-doll thickness)
doll.scale = (1.0, 1.0, 0.7)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Move to the main's center, scale to match main's height
# Already at world position (since we transformed with matrix_world)
# But need to verify scale matches
print(f"  doll bbox: {doll.dimensions}")
print(f"  doll verts: {len(doll.data.vertices)}")

# Save intermediate
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "intermediate_with_doll.blend"))

# Render doll alone
render_png("03_doll_only_diag.png", only_objs={"doll"}, view="diag")
render_png("03_doll_only_front.png", only_objs={"doll"}, view="front")
render_png("03_doll_only_back.png", only_objs={"doll"}, view="back")

# ------------------------------------------------------------------
# STEP 9: Replace main's person content with the doll
#         (Hide original main parts, show doll + extracted parts)
# ------------------------------------------------------------------
print("\n=== STEP 9: hide main person (keep base + decorations) ===")
# Hide body/head from main (the person content) but keep base + extracted parts
for p in main_parts:
    # Hide the "person" parts (those that contribute to body/head)
    # parts 2 (hair), 7 (mantle), 8 (dress), 1 (lyre?), 5 (hand?), 6 (detail?)
    if p.name in {"part_1.001", "part_2.001", "part_5.001", "part_6.001", "part_7.001", "part_8.001"}:
        p.hide_render = True
        p.hide_viewport = True

# Move extracted parts back to visible
for p in [hair_obj, fabric_obj, body_obj, head_obj, base_obj]:
    if p:
        p.hide_render = False
        p.hide_viewport = False

# Position the doll at main's center
doll.location = (center_main.x, center_main.y, center_main.z)
print(f"  doll moved to {doll.location}")

render_png("04_doll_substituted_diag.png", view="diag")
render_png("04_doll_substituted_front.png", view="front")
render_png("04_doll_substituted_back.png", view="back")

# ------------------------------------------------------------------
# STEP 10: Bring in decoration1 (Mesh_0) and decoration2 (Mesh_0.001)
# ------------------------------------------------------------------
print("\n=== STEP 10: bring in decorations ===")
dec1 = bpy.data.objects.get("Mesh_0")    # flat lyre silhouette
dec2 = bpy.data.objects.get("Mesh_0.001")  # long 3D strip
if dec1:
    # Position to the LEFT of main, scaled down to a decoration size
    # Mesh_0 is at x=-1.42; let's move it near the figure (front)
    dec1.location = (center_main.x + 0.0, center_main.y - size_main * 0.8, center_main.z + size_main * 0.3)
    dec1.scale = (size_main * 0.5, 1.0, size_main * 0.5)  # scale to ~50% of figure
    dec1.hide_render = False
    dec1.hide_viewport = False
    print(f"  decoration1 (Mesh_0) at {dec1.location}, scale={dec1.scale}")
if dec2:
    dec2.location = (center_main.x + 0.0, center_main.y + size_main * 0.8, center_main.z + size_main * 0.2)
    dec2.scale = (size_main * 0.6, size_main * 0.6, size_main * 0.6)
    dec2.hide_render = False
    dec2.hide_viewport = False
    print(f"  decoration2 (Mesh_0.001) at {dec2.location}, scale={dec2.scale}")

# ------------------------------------------------------------------
# STEP 11: Final render + save
# ------------------------------------------------------------------
print("\n=== STEP 11: final render + save ===")
render_png("05_final_diag.png", view="diag")
render_png("05_final_front.png", view="front")
render_png("05_final_back.png", view="back")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "final.blend"))

# Print summary
print("\n=== SUMMARY ===")
print(f"  main parts: {len(main_parts)} (original)")
print(f"  extracted: hair, fabric, body, head, base")
print(f"  doll: {doll.name} ({len(doll.data.vertices)} verts)")
print(f"  decorations: Mesh_0 (decoration1), Mesh_0.001 (decoration2)")
print(f"  output dir: {OUT_DIR}")
print(f"  final file: {OUT_DIR}/final.blend")
