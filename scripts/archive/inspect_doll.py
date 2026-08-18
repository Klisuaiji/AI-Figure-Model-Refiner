"""Inspect what the doll has after the workflow."""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\Qq203\Downloads\AI Figure Model Refiner\output\workflow_demo\intermediate_with_doll.blend")
doll = bpy.data.objects.get("doll")
if doll is None:
    print("No doll!")
else:
    print(f"Doll: {doll.name}")
    print(f"  verts: {len(doll.data.vertices)}")
    print(f"  materials: {[m.name for m in doll.data.materials]}")
    print(f"  color_attributes:")
    for ca in doll.data.color_attributes:
        print(f"    {ca.name}: domain={ca.domain}, data_type={ca.data_type}")
        if ca.data:
            # sample 3 colors
            sample = [ca.data[i].color[:] for i in range(min(3, len(ca.data)))]
            print(f"      sample colors: {sample}")
    print(f"  render_color_index: {doll.data.color_attributes.render_color_index}")
    print(f"  active_material: {doll.active_material.name if doll.active_material else None}")
