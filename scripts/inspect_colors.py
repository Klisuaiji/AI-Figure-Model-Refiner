"""Inspect original parts' color attributes."""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")
for p in bpy.data.objects:
    if p.type != "MESH" or not p.name.startswith("part_"):
        continue
    print(f"=== {p.name} ===")
    print(f"  materials: {[m.name for m in p.data.materials]}")
    for ca in p.data.color_attributes:
        sample = [ca.data[i].color[:] for i in range(min(3, len(ca.data)))]
        print(f"  color attr: {ca.name} domain={ca.domain} data_type={ca.data_type}")
        print(f"    sample: {sample}")
    print(f"  render_color_index: {p.data.color_attributes.render_color_index}")
