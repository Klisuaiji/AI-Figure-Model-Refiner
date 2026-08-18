"""V10 - 真正的二次元笔触：剔除游离细刺 + 二次元流线化。

策略:
  1. 找到最大的 component (190k 顶点, 主体头发)
  2. 算它的 bbox 中心和半径
  3. 任何 vertex 距离中心 > 主块 bbox_max_extent * 1.5 就视为"游离细刺"
     （这些是看似连接但实际上从远处扎入细长管的顶点）
  4. 删面、填洞、Laplacian、solidify、toon
"""
import bpy
import bmesh
import os
import sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "..", "output", "anime_workflow_v3")
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, ADDON_DIR)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

hair = bpy.data.objects.get("part_2.001")
print(f"--- V10: distance-based spike removal ---")
print(f"  Hair: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

bm = bmesh.new()
bm.from_mesh(hair.data)
bm.edges.ensure_lookup_table()

# ---------- STEP 1: 找最大连通分量 ----------
print("\n=== STEP 1: largest component ===")
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
main_comp = components[0]
print(f"  main comp: {len(main_comp)} verts (from {len(components)} total)")

# ---------- STEP 2: 主体块的 bbox 中心和最大延伸 ----------
# 使用 bbox 中心 (几何居中) 而非质心 (顶点偏向密集区)
all_coords = [v.co for v in main_comp]
xs = [c.x for c in all_coords]
ys = [c.y for c in all_coords]
zs = [c.z for c in all_coords]
bbox_center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
main_extents = (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
max_extent = max(main_extents)
print(f"  main bbox center: {bbox_center}")
print(f"  main extents: {main_extents}, max={max_extent:.4f}")
print(f"  main vertex range: x=[{min(xs):.3f},{max(xs):.3f}] y=[{min(ys):.3f},{max(ys):.3f}] z=[{min(zs):.3f},{max(zs):.3f}]")

# ---------- STEP 3: 检测游离顶点（远距主体块 bbox 中心）----------
# 用 1.5×bbox max_extent 作为硬阈值：细刺（细线状顶点）
# 会伸出 bbox 1.5 倍之外；正常头发/发尖则在 bbox 内或附近
DISTANCE_THRESHOLD = max_extent * 0.55  # bbox max 的 0.55 倍
print(f"\n=== STEP 3: distant vertex filter (threshold={DISTANCE_THRESHOLD:.4f} = max_extent * 0.55) ===")

# 调试：先打印最远的 10 个 vertex
all_dists = sorted([((v.co - bbox_center).length, v.co) for v in bm.verts], reverse=True)
print(f"  Top-5 farthest vertices (from bbox_center):")
for d, c in all_dists[:5]:
    print(f"    d={d:.4f}, co={tuple(round(x,3) for x in c)}")

distant_verts = set()
for v in bm.verts:
    d = (v.co - bbox_center).length
    if d > DISTANCE_THRESHOLD:
        distant_verts.add(v)

# 也算"细刺"：边长 > 主体平均边长 5 倍的边
main_edges = [e for e in bm.edges if all(v in main_comp for v in e.verts)]
if main_edges:
    avg_main_edge = sum(e.calc_length() for e in main_edges) / len(main_edges)
    long_edges = [e for e in bm.edges if e.calc_length() > avg_main_edge * 8]
    # 端点是 distant_verts
    for e in long_edges:
        for v in e.verts:
            if (v.co - main_center).length > max_extent * 0.7:
                distant_verts.add(v)
    print(f"  avg main edge: {avg_main_edge:.5f}, long edges: {len(long_edges)}")
print(f"  distant verts: {len(distant_verts)}")

# ---------- STEP 4: 删除远距顶点相关的面 ----------
print(f"\n=== STEP 4: delete distant vertex faces ===")
distant_face_list = [f for f in bm.faces if any(v in distant_verts for v in f.verts)]
print(f"  faces to delete: {len(distant_face_list)}")
if distant_face_list:
    bmesh.ops.delete(bm, geom=distant_face_list, context='FACES_KEEP_BOUNDARY')
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After delete: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 5: 二次填洞（V9 留下的孔）----------
print("\n=== STEP 5: re-fill holes ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 6: Laplacian smooth factor 0.12 x 2 ----------
print("\n=== STEP 6: smooth factor 0.12 x2 ===")
for it in range(2):
    bm = bmesh.new()
    bm.from_mesh(hair.data)
    bmesh.ops.smooth_vert(
        bm, verts=list(bm.verts), factor=0.12,
        use_axis_x=True, use_axis_y=True, use_axis_z=True,
    )
    bm.to_mesh(hair.data)
    bm.free()
    hair.data.update()
print(f"  After 2x smooth: dims={list(hair.dimensions)}")

# ---------- STEP 7: 再次填洞（smooth 可能打开小孔）----------
print("\n=== STEP 7: re-fill after smooth ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After re-fill: {len(hair.data.vertices)} verts")

# ---------- STEP 8: Solidify 2mm (slightly thicker for print) ----------
print("\n=== STEP 8: solidify 2mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.shade_smooth()
bpy.ops.object.modifier_add(type='SOLIDIFY')
mod_sol = hair.modifiers[-1]
mod_sol.thickness = 0.002
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
bpy.ops.object.modifier_apply(modifier=mod_sol.name)
hair.select_set(False)
print(f"  After solidify: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 9: Toon material ----------
print("\n=== STEP 9: toon material ===")
mat = bpy.data.materials.new("AFR_Hair_V10")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.92, 0.92, 0.95, 1.0)  # silver anime
bsdf.inputs["Roughness"].default_value = 0.5
# Sheen for anime hair
for sheen in ("Sheen Weight", "Sheen"):
    if sheen in bsdf.inputs:
        bsdf.inputs[sheen].default_value = 0.6
        break
hair.data.materials.clear()
hair.data.materials.append(mat)
hair.data.color_attributes.render_color_index = -1

# ---------- STEP 10: Render ----------
print("\n=== STEP 10: render ===")
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True

if "Sun" not in bpy.data.objects:
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 4.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)

if "Camera" not in bpy.data.objects:
    bpy.ops.object.camera_add(location=(0, -3, 0))
    bpy.context.scene.camera = bpy.context.view_layer.objects.active
    bpy.context.scene.camera.data.lens = 35

# Hide everything except hair
for o in bpy.data.objects:
    if o.type == "MESH" and o != hair:
        o.hide_render = True
        o.hide_viewport = True

cam = bpy.context.scene.camera
bb = [hair.matrix_world @ Vector(c) for c in hair.bound_box]
center = sum(bb, Vector((0,0,0))) / len(bb)
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
print(f"  center={center}, size={size}")

for view_name, off in [
    ("diag", (size*1.0, -size*1.0, size*0.4)),
    ("front", (0, -size*1.6, 0)),
    ("side", (size*1.6, 0, 0)),
    ("back", (0, size*1.6, 0)),
]:
    cam.location = (center.x + off[0], center.y + off[1], center.z + off[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    out_path = os.path.join(OUT_DIR, f"hair_v10_{view_name}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  saved {out_path}")

# Save
out_blend = os.path.join(OUT_DIR, "hair_anime_v10.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"\n=== SAVED {out_blend} ===")
print(f"  final verts: {len(hair.data.vertices)}")
print(f"  final dims: {list(hair.dimensions)}")
