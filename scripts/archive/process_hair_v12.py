"""V12 - V4 基础上剔除细长面（spike 杀手）。

V4 流程 (decimate 0.04 + fill) 主体形状 OK，但有 5-6 根 1D 细刺
（看起来像鱿鱼须）。

策略: 用 bmesh 检测每个 face 的 thinness
  thinness = max_edge_length / sqrt(face_area)
  刺的面：thinness > 6 (一维管状三角形)
  主体面：thinness < 3 (二维片状)

逐步:
  1. decimate 0.04 (V4 流程)
  2. holes_fill
  3. 检测 thinness 高的 face，标为 spike face
  4. BFS 扩散：和 spike face 共边相连的 face 也删除（避免刺断根）
  5. dissolve_verts 移除孤立的刺端点
  6. holes_fill 重新填洞
  7. light Laplacian smooth (factor 0.10)
  8. solidify 2mm
  9. toon material
"""
import bpy, bmesh, os, sys, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "..", "output", "anime_workflow_v3")
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, ADDON_DIR)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

hair = bpy.data.objects.get("part_2.001")
print(f"--- V12: V4 + spike face removal ---")
print(f"  Hair: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 1: decimate 0.04 (V4 一样的核心) ----------
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

# ---------- STEP 2: holes_fill (V4 一样) ----------
print("\n=== STEP 2: holes fill ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 3: detect thin spike faces ----------
print("\n=== STEP 3: detect thin spike faces ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bm.faces.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.verts.ensure_lookup_table()

# face thinness = max_edge / sqrt(face_area)
def face_thinness(f):
    edges = f.edges
    if not edges:
        return 0.0
    max_e = max(e.calc_length() for e in edges)
    area = f.calc_area()
    if area < 1e-8:
        return 999.0
    return max_e / math.sqrt(area)

# 统计 face thinness
all_thinness = [(f, face_thinness(f)) for f in bm.faces]
all_thinness.sort(key=lambda x: -x[1])
print(f"  total faces: {len(all_thinness)}")
print(f"  thinness distribution:")
thresholds = [3, 4, 5, 6, 8, 10, 15, 20]
for t in thresholds:
    n = sum(1 for _, th in all_thinness if th > t)
    print(f"    > {t}: {n} faces ({n*100/len(all_thinness):.1f}%)")

# 取 thinness > 6 的 face 为 spike
SPIKE_THRESHOLD = 6.0
spike_face_set = set(f for f, t in all_thinness if t > SPIKE_THRESHOLD)
print(f"\n  spike faces (thinness > {SPIKE_THRESHOLD}): {len(spike_face_set)}")

# ---------- STEP 4: BFS 扩张：相邻的 thin face 也算刺 ----------
# 不需要太激进，1 跳 BFS 即可
print("\n=== STEP 4: BFS expand spike region ===")
expanded_spike = set(spike_face_set)
for f in spike_face_set:
    for e in f.edges:
        for other_f in e.link_faces:
            if other_f not in expanded_spike:
                # 只扩张 thinness > 4 的相邻面（避免吃主体）
                if face_thinness(other_f) > 4.0:
                    expanded_spike.add(other_f)
print(f"  After BFS expansion: {len(expanded_spike)} spike faces")

# ---------- STEP 5: delete spike faces + dissolve isolated verts ----------
print("\n=== STEP 5: delete spike faces ===")
bmesh.ops.delete(bm, geom=list(expanded_spike), context='FACES_KEEP_BOUNDARY')
# 删除孤立顶点
bm.verts.ensure_lookup_table()
orphan_verts = [v for v in bm.verts if len(v.link_faces) == 0]
print(f"  orphan verts to dissolve: {len(orphan_verts)}")
if orphan_verts:
    bmesh.ops.dissolve_verts(bm, verts=orphan_verts)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After spike delete: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 6: re-fill holes ----------
print("\n=== STEP 6: re-fill holes ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ---------- STEP 7: light Laplacian smooth ----------
print("\n=== STEP 7: smooth factor 0.10 x1 ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.10,
                      use_axis_x=True, use_axis_y=True, use_axis_z=True)
bm.to_mesh(hair.data)
bm.free()
hair.data.update()
print(f"  After smooth: dims={list(hair.dimensions)}")

# ---------- STEP 8: re-fill holes after smooth ----------
print("\n=== STEP 8: re-fill after smooth ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()

# ---------- STEP 9: solidify 2mm ----------
print("\n=== STEP 9: solidify 2mm ===")
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

# ---------- STEP 10: toon material ----------
print("\n=== STEP 10: toon material ===")
mat = bpy.data.materials.new("AFR_Hair_V12")
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

# ---------- STEP 11: render ----------
print("\n=== STEP 11: render ===")
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
    out_path = os.path.join(OUT_DIR, f"hair_v12_{view_name}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  saved {out_path}")

out_blend = os.path.join(OUT_DIR, "hair_anime_v12.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"\n=== SAVED {out_blend} ===")
print(f"  final verts: {len(hair.data.vertices)}")
print(f"  final dims: {list(hair.dimensions)}")
