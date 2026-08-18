"""Re-inspect D:\未命名.blend current state."""
import bpy
import json

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

out = {"collections": [], "objects": []}
for c in bpy.data.collections:
    out["collections"].append({
        "name": c.name,
        "objects": [o.name for o in c.objects],
    })
for o in bpy.data.objects:
    info = {
        "name": o.name,
        "type": o.type,
        "location": list(o.location),
    }
    if o.type == "MESH" and o.data:
        info["vertices"] = len(o.data.vertices)
        info["faces"] = len(o.data.polygons)
        info["bbox_size"] = list(o.dimensions)
    out["objects"].append(info)
print(json.dumps(out, indent=2, ensure_ascii=False))
