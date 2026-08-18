"""Test: just apply solidify 1.5mm to hair, see if it inflates."""
import bpy
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "hair_only.blend"))

hair = bpy.data.objects.get("part_2.001")
print(f"Before: verts={len(hair.data.vertices)}, dims={hair.dimensions}")

# Just solidify, no smoothing
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
bpy.ops.object.modifier_apply(modifier="PrintSolidify")
hair.select_set(False)
print(f"After solidify: verts={len(hair.data.vertices)}, dims={hair.dimensions}")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_solid_only.blend"))
