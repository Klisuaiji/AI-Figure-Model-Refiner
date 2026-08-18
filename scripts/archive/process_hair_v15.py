"""V15 - V4 基础 + 剔刺 + toon 材质（不动 solidity）。

跳过：holes_fill, solidify（它们在剔刺后留下非 manifold，导致问题）
保留：decimate 0.04, 剔刺, 轻 smooth, toon material
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
print(f"--- V15: V4 + spike cut + toon (no solidify) ---")
print(f"  Hair: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 1: decimate 0.04 ----------
print("\n=== STEP 1: decimate 0.04 ===")
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

# ---------- STEP 2: holes fill (V4 一样的) ----------
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

# ---------- STEP 3: find core + far vertices ----------
print("\n=== STEP 3: identify spike vertices ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bm.verts.ensure_lookup_table()

# core = median
all_coords = [v.co for v in bm.verts]
xs = sorted(c.x for c in all_coords)
ys = sorted(c.y for c in all_coords)
zs = sorted(c.z for c in all_coords)
n = len(all_coords)
core_center = Vector((xs[n//2], ys[n//2], zs[n//2]))
print(f"  core: {core_center}")
print(f"  bbox: x=[{xs[0]:.3f},{xs[-1]:.3f}] y=[{ys[0]:.3f},{ys[-1]:.3f}] z=[{zs[0]:.3f},{zs[-1]:.3f}]")

# 距离分布
all_dists = sorted([((v.co - core_center).length, v) for v in bm.verts], reverse=True)
print(f"  Top 5 farthest:")
for d, v in all_dists[:5]:
    print(f"    d={d:.3f}, co={tuple(round(x,3) for x in v.co)}")
p95 = all_dists[int(n*0.05)][0]
p90 = all_dists[int(n*0.10)][0]
print(f"  percentile 90: {p90:.3f}, 95: {p95:.3f}")

# 用 90 percentile 阈值：超过 90% 距离的 vertex 视为 spike 端点
DIST_THRESHOLD = p90 * 1.15
print(f"  threshold: {DIST_THRESHOLD:.3f} (p90 * 1.15)")

far_verts = set()
for v in bm.verts:
    if (v.co - core_center).length > DIST_THRESHOLD:
        far_verts.add(v)
print(f"  far verts: {len(far_verts)}")

# ---------- STEP 4: BFS-extend through narrow triangles ----------
# 任何 face 含 ≥1 far_vert 且 thinness > 4 的视为 spike
print("\n=== STEP 4: BFS extend via thinness ===")
spike_faces = set()
for f in bm.faces:
    if any(v in far_verts for v in f.verts):
        # check thinness
        if len(f.verts) >= 3:
            edges = [e.calc_length() for e in f.edges]
            max_e = max(edges)
            area = f.calc_area()
            thinness = max_e / (area**0.5) if area > 1e-8 else 999
            if thinness > 3.0:
                spike_faces.add(f)

# BFS: spike face 的邻居 thin face 也算
queue = list(spike_faces)
spike_region = set(spike_faces)
while queue:
    f = queue.pop()
    for e in f.edges:
        for nf in e.link_faces:
            if nf in spike_region:
                continue
            if len(nf.verts) >= 3:
                edges = [ee.calc_length() for ee in nf.edges]
                max_e = max(edges)
                area = nf.calc_area()
                thinness = max_e / (area**0.5) if area > 1e-8 else 999
                if thinness > 3.0 and any(v in far_verts for v in nf.verts):
                    spike_region.add(nf)
                    queue.append(nf)
print(f"  spike region: {len(spike_region)} faces")

# ---------- STEP 5: delete spike region (keep boundary) ----------
print(f"\n=== STEP 5: delete spike faces ===")
if spike_region:
    bmesh.ops.delete(bm, geom=list(spike_region), context='FACES_KEEP_BOUNDARY')
bm.verts.ensure_lookup_table()
orphan_verts = [v for v in bm.verts if len(v.link_faces) == 0]
print(f"  orphan verts: {len(orphan_verts)}")
if orphan_verts:
    bmesh.ops.dissolve_verts(bm, verts=orphan_verts)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After spike delete: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 6: re-fill holes (the deletion created new boundaries) ----------
print("\n=== STEP 6: re-fill after spike cut ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ---------- STEP 7: light smooth ----------
print("\n=== STEP 7: smooth factor 0.10 x1 ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.10,
                      use_axis_x=True, use_axis_y=True, use_axis_z=True)
bm.to_mesh(hair.data)
bm.free()
hair.data.update()
print(f"  After smooth: dims={list(hair.dimensions)}")

# ---------- STEP 8: toon material ----------
print("\n=== STEP 8: toon material ===")
mat = bpy.data.materials.new("AFR_Hair_V15")
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

# ---------- STEP 9: render ----------
print("\n=== STEP 9: render ===")
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
    out_path = os.path.join(OUT_DIR, f"hair_v15_{view_name}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  saved {out_path}")

out_blend = os.path.join(OUT_DIR, "hair_anime_v15.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"\n=== SAVED {out_blend} ===")
print(f"  final verts: {len(hair.data.vertices)}")
print(f"  final dims: {list(hair.dimensions)}")
