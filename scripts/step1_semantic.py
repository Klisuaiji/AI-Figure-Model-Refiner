"""Apply semantic labels to main's parts and dump what got labeled."""
import bpy
import os
import sys
import json

# Add addon path explicitly
ADDON_PARENT = r"D:\Qq203\Downloads\AI Figure Model Refiner\addon"
if ADDON_PARENT not in sys.path:
    sys.path.append(ADDON_PARENT)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

import ai_figure_refiner
ai_figure_refiner.register()

# Set source = part cluster
parts = [o for o in bpy.data.objects if o.name.startswith("part_")]
for o in bpy.data.objects:
    o.select_set(o in parts)
bpy.context.view_layer.objects.active = parts[0] if parts else None

# Set source via operator
bpy.ops.afr.use_selected()

# Run diagnostics first to see what we have
print("=== Run diagnostics ===")
try:
    bpy.ops.afr.run_diagnostics()
    diag = bpy.context.scene.afr_diag_json
    print(diag[:1500])
except Exception as e:
    print(f"diag failed: {e}")

# Apply semantic heuristics
print("\n=== Apply semantic heuristics ===")
try:
    bpy.ops.afr.semantic_apply_heuristics()
except Exception as e:
    print(f"semantic failed: {e}")
    import traceback
    traceback.print_exc()

# Dump per-object labels
print("\n=== Per-object labels after heuristics ===")
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    label_attr = o.get("afr_label") or o.get("afr_part_label")
    label_face = o.get("afr_face_label") or o.get("afr_labels")
    faces_with = 0
    if o.data and "afr_label" in o.data:
        labels = o.data["afr_label"]
        labels = list(set(labels))
        faces_with = len([l for l in labels if l])
        print(f"  {o.name}: faces with label = {labels[:10]}")
    if label_attr is not None:
        print(f"  {o.name}: obj.label = {label_attr}")
    print(f"  {o.name}: obj keys = {list(o.keys())}")
    if o.data:
        print(f"    mesh keys = {list(o.data.keys())}")
        for k in o.data.keys():
            if "afr" in k.lower() or "label" in k.lower() or "semantic" in k.lower():
                print(f"    mesh['{k}'] = {type(o.data[k])}")
