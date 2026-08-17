"""Inspect D:\未命名.blend — list all collections, objects, mesh stats."""
import bpy
import sys

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

out = {"collections": [], "objects": [], "meshes": []}

def walk(col, depth=0):
    out["collections"].append({
        "name": col.name,
        "depth": depth,
        "children": [c.name for c in col.children],
        "objects": [o.name for o in col.objects],
    })
    for c in col.children:
        walk(c, depth + 1)

for c in bpy.data.collections:
    walk(c)

for o in bpy.data.objects:
    info = {
        "name": o.name,
        "type": o.type,
        "collections": [c.name for c in o.users_collection],
        "location": list(o.location),
    }
    if o.type == "MESH" and o.data:
        info["vertices"] = len(o.data.vertices)
        info["faces"] = len(o.data.polygons)
        info["bbox"] = [list(o.bound_box[0]), list(o.bound_box[6])]
    out["objects"].append(info)

for m in bpy.data.meshes:
    out["meshes"].append({
        "name": m.name,
        "vertices": len(m.vertices),
        "faces": len(m.polygons),
        "users": [o.name for o in bpy.data.objects if o.data == m],
    })

import json
print(json.dumps(out, indent=2, ensure_ascii=False))
