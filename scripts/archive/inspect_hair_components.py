"""Inspect ALL components, not just main."""
import bpy, bmesh
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

hair = bpy.data.objects.get("part_2.001")
bm = bmesh.new()
bm.from_mesh(hair.data)

# Connected components
visited = set()
components = []
for v in bm.verts:
    if v in visited:
        continue
    stack = [v]
    comp = set()
    while stack:
        x = stack.pop()
        if x in visited:
            continue
        visited.add(x)
        comp.add(x)
        for e in x.link_edges:
            o = e.other_vert(x)
            if o not in visited:
                stack.append(o)
    components.append(comp)

components.sort(key=len, reverse=True)
print(f"\nTotal components: {len(components)}")
for i, comp in enumerate(components):
    coords = [v.co for v in comp]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    bbox = (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    aniso = max(bbox) / max(min(b for b in bbox if b > 0.001) if any(b > 0.001 for b in bbox) else 0.001, 0.001)
    if len(comp) < 3:
        print(f"  comp[{i}]: verts={len(comp):5d}, bbox={bbox}")
        continue
    print(f"  comp[{i}]: verts={len(comp):5d}, "
          f"bbox=({bbox[0]:.3f},{bbox[1]:.3f},{bbox[2]:.3f}), "
          f"aniso={aniso:.2f}, "
          f"center=({(min(xs)+max(xs))/2:.3f}, {(min(ys)+max(ys))/2:.3f}, {(min(zs)+max(zs))/2:.3f})")
