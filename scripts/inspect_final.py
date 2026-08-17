"""Inspect final.blend — what's actually visible in the final scene?"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\Qq203\Downloads\AI Figure Model Refiner\output\workflow_demo\final.blend")
for o in bpy.data.objects:
    if o.type == "MESH":
        print(f"=== {o.name} ===")
        print(f"  hide_render: {o.hide_render}")
        print(f"  hide_viewport: {o.hide_viewport}")
        print(f"  materials: {[m.name for m in o.data.materials]}")
        ca = list(o.data.color_attributes.keys())
        print(f"  color attrs: {ca}")
        print(f"  render_color_index: {o.data.color_attributes.render_color_index}")
        if "AFR_DollMat" in [m.name for m in o.data.materials]:
            print("  ---> DOLL MATERIAL")
        if "AFR_Dec1" in [m.name for m in o.data.materials]:
            print("  ---> DEC1 MATERIAL")
        if "AFR_Dec2" in [m.name for m in o.data.materials]:
            print("  ---> DEC2 MATERIAL")
