"""Use modifier-based Smooth (Laplacian) + apply + Solidify. Modifier
smooth is the same operator but bmesh.ops.smooth_vert might be the issue."""
import bpy
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "hair_only.blend"))

hair = bpy.data.objects.get("part_2.001")
print(f"Before: verts={len(hair.data.vertices)}, dims={hair.dimensions}")

# Try bmesh.ops.smooth_vert with smaller factor
import bmesh
for it in range(3):
    bm = bmesh.new()
    try:
        bm.from_mesh(hair.data)
        bmesh.ops.smooth_vert(
            bm, verts=list(bm.verts),
            factor=0.1,  # very small factor
            use_axis_x=True, use_axis_y=True, use_axis_z=True,
        )
        bm.to_mesh(hair.data)
    finally:
        bm.free()
    hair.data.update()
    print(f"  iter {it+1} (factor=0.1): dims={hair.dimensions}")

# Solidify
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
mod_sol = hair.modifiers.new("PrintSolidify", "SOLIDIFY")
mod_sol.thickness = 0.0015
bpy.ops.object.modifier_apply(modifier="PrintSolidify")
hair.select_set(False)
print(f"After solidify: verts={len(hair.data.vertices)}, dims={hair.dimensions}")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "hair_smooth_010.blend"))
