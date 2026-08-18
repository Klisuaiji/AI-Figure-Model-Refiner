"""V14 - V4 流程 + 删"远离主体中心"的细管末梢。

诊断：V4 (decimate 0.04) 后所有刺都在 main comp 内
  (它们是 comp[0] 内部通过狭窄连接连到主体的细管)

策略:
  1. decimate 0.04 (V4 流程)
  2. holes fill
  3. 找所有 vertex
  4. 找主体 comp 顶点的"密集团心" = core_center
  5. 算每个 vertex 离 core_center 的距离
  6. 距离 > threshold = 远端 vertex
  7. 删这些 vertex 相关的面
  8. dissolve 孤立 vertex
  9. re-fill holes
  10. solidify 2mm
  11. toon
"""
import bpy, bmesh, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "..", "output", "anime_workflow_v3")
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, ADDON_DIR)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

hair = bpy.data.objects.get("part_2.001")
print(f"--- V14: V4 + far-vertex removal ---")
print(f"  Hair: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 1: decimate 0.04 ----------
print("\n=== STEP 1: decimate 0.04 (collapse) ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.shade_smooth()
bpy.ops.object.modifier_add(type='DECIMATE')
mod_dec = hair.modifiers["Decimate"]
mod_dec.ratio = 0.04
mod_dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="Decimate")
hair.select_set(False)
print(f"  After decimate: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 2: holes fill ----------
print("\n=== STEP 2: holes fill ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ---------- STEP 3: find core center (densest region) ----------
print("\n=== STEP 3: find core (densest region) ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bm.verts.ensure_lookup_table()

# core = 80% 中心化的 vertex: 用 median
all_coords = [v.co for v in bm.verts]
xs = sorted(c.x for c in all_coords)
ys = sorted(c.y for c in all_coords)
zs = sorted(c.z for c in all_coords)
n = len(all_coords)
# median = the middle value
core_center = Vector((xs[n//2], ys[n//2], zs[n//2]))
print(f"  vertex count: {n}")
print(f"  core (median): {core_center}")
print(f"  bbox: x=[{xs[0]:.3f},{xs[-1]:.3f}], y=[{ys[0]:.3f},{ys[-1]:.3f}], z=[{zs[0]:.3f},{zs[-1]:.3f}]")

# 距离分布
all_dists = sorted([((v.co - core_center).length, v.co) for v in bm.verts], reverse=True)
print(f"  Top 10 farthest vertices from core:")
for d, c in all_dists[:10]:
    print(f"    d={d:.3f}, co={tuple(round(x,3) for x in c)}")
# percentile 90
p90 = all_dists[int(n*0.1)][0]
p95 = all_dists[int(n*0.05)][0]
p99 = all_dists[int(n*0.01)][0]
print(f"  percentile 90: {p90:.3f}, 95: {p95:.3f}, 99: {p99:.3f}")

# 距离主体中心 + 一些容差
# 用 95 percentile 作为阈值：超出 5% 的 vertex 视为 spike
DIST_THRESHOLD = p95 * 1.05
print(f"  threshold = {DIST_THRESHOLD:.3f} (p95 * 1.05)")

# ---------- STEP 4: identify far vertices ----------
far_verts = set()
for v in bm.verts:
    d = (v.co - core_center).length
    if d > DIST_THRESHOLD:
        far_verts.add(v)
print(f"\n  far verts: {len(far_verts)}")

# 找这些 far_verts 相关的 face
far_faces = set()
for f in bm.faces:
    if any(v in far_verts for v in f.verts):
        far_faces.add(f)
print(f"  far faces: {len(far_faces)}")

# 调试: 打印最远 5 个 vertex 周围的面
print(f"  Far vertex neighbor faces (sample 3):")
for i, v in enumerate(list(far_verts)[:3]):
    print(f"    vert {v.co} has {len(v.link_faces)} link_faces")

# ---------- STEP 5: BFS extend - delete "fingers" of far faces ----------
# 不只删 far 顶点相关的面，延伸到 far 顶点指向主体的"细管"
# BFS: 任何只有 1 个 far_vert 在内、且其它 vert 是中等距离的 face 也算 spike
print("\n=== STEP 5: BFS-extend spike region ===")
# BFS from far_faces, expanding to faces that have ≥1 far_vert AND are
# 'narrow' (thinness > some threshold)
spike_region = set(far_faces)
queue = list(far_faces)
while queue:
    f = queue.pop()
    for e in f.edges:
        for nf in e.link_faces:
            if nf in spike_region or nf in far_faces:
                continue
            # check if this face is "narrow" (long thin triangle)
            if len(nf.verts) >= 3:
                edges = [ee.calc_length() for ee in nf.edges]
                if edges:
                    max_e = max(edges)
                    area = nf.calc_area()
                    thinness = max_e / (area ** 0.5) if area > 1e-8 else 999
                    if thinness > 4.0:  # narrow
                        spike_region.add(nf)
                        queue.append(nf)
print(f"  spike region size: {len(spike_region)}")

# ---------- STEP 6: delete spike region ----------
print(f"\n=== STEP 6: delete spike faces ===")
bmesh.ops.delete(bm, geom=list(spike_region), context='FACES_KEEP_BOUNDARY')
bm.verts.ensure_lookup_table()
orphan_verts = [v for v in bm.verts if len(v.link_faces) == 0]
print(f"  orphan verts to dissolve: {len(orphan_verts)}")
if orphan_verts:
    bmesh.ops.dissolve_verts(bm, verts=orphan_verts)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After spike delete: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 7: re-fill holes ----------
print("\n=== STEP 7: re-fill holes ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ---------- STEP 8: light smooth ----------
print("\n=== STEP 8: smooth factor 0.10 x1 ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.10,
                      use_axis_x=True, use_axis_y=True, use_axis_z=True)
bm.to_mesh(hair.data)
bm.free()
hair.data.update()

# ---------- STEP 9: re-fill after smooth ----------
print("\n=== STEP 9: re-fill after smooth ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()

# ---------- STEP 10: solidify 2mm ----------
print("\n=== STEP 10: solidify 2mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.shade_smooth()
bpy.ops.object.modifier_add(type='SOLIDIFY')
sol = hair.modifiers[-1]
sol.thickness = 0.002
sol.offset = 0.0
sol.use_even_offset = True
bpy.ops.object.modifier_apply(modifier=sol.name)
hair.select_set(False)
print(f"  After solidify: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 11: toon material ----------
print("\n=== STEP 11: toon material ===")
mat = bpy.data.materials.new("AFR_Hair_V14")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.92, 0.92, 0.95, 1.0)
bsdf.inputs["Roughness"].default_value = 0.5
for sheen in ("Sheen Weight", "Sheen"):
    if sheen in bsdf.inputs:
        bsdf.inputs[sheen].default_value = 0.6
        break
hair.data.materials.clear()
hair.data.materials.append(mat)
try:
    hair.data.color_attributes.render_color_index = -1
except Exception:
    pass

# ---------- STEP 12: render ----------
print("\n=== STEP 12: render ===")
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
if "Sun" not in bpy.data.objects:
    ld = bpy.data.lights.new("Sun", type="SUN"); ld.energy = 4.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo); lo.location = (3, -3, 5)
if "Camera" not in bpy.data.objects:
    bpy.ops.object.camera_add(location=(0, -3, 0))
    bpy.context.scene.camera = bpy.context.view_layer.objects.active
    bpy.context.scene.camera.data.lens = 35

for o in bpy.data.objects:
    if o.type == "MESH" and o != hair:
        o.hide_render = True; o.hide_viewport = True

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
    cam.location = (center.x+off[0], center.y+off[1], center.z+off[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    out_path = os.path.join(OUT_DIR, f"hair_v14_{view_name}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  saved {out_path}")

out_blend = os.path.join(OUT_DIR, "hair_anime_v14.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"\n=== SAVED {out_blend} ===")
print(f"  final verts: {len(hair.data.vertices)}")
print(f"  final dims: {list(hair.dimensions)}")
