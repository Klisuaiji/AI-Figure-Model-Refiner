"""V9 - 真正的二次元笔触化头发。

问题分析：原始头发包含两种几何体
  (a) 主要的块状头发主体（需要保留）
  (b) 突出的细长尖刺（"鱿鱼须"的来源，需要删除）

判断方式：每个 connected component 的 bounding box 长宽比（anisotropy）
  - 主要头发块: 长宽比 < 3（接近球形）
  - 细长尖刺: 长宽比 > 5（一维突出）
"""
import bpy
import bmesh
import os
import sys
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "..", "output", "anime_workflow_v3")
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, ADDON_DIR)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

hair = bpy.data.objects.get("part_2.001")
if hair is None:
    raise SystemExit("hair (part_2.001) not found")

print(f"--- V9: smart spike removal ---")
print(f"  Hair: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# 渲染材料：toon
def setup_toon_material(obj, color=(0.85, 0.85, 0.92), name="AFR_ToonHair"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    # color is (r, g, b) — add alpha 1.0
    if len(color) == 3:
        color = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.5
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    obj.data.color_attributes.render_color_index = -1
    return mat


# ---------- STEP 1: 用 bmesh + flood-fill 找连通分量 ----------
print("\n=== STEP 1: identify connected components ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bm.edges.ensure_lookup_table()

# 给每个 vert 打 component label (BFS)
components = []  # list of sets of BMVerts
visited = set()

def flood_fill(start_vert, label):
    stack = [start_vert]
    component = set()
    while stack:
        v = stack.pop()
        if v in visited:
            continue
        visited.add(v)
        component.add(v)
        for e in v.link_edges:
            other = e.other_vert(v)
            if other not in visited:
                stack.append(other)
    return component

# 用 indexing: BMVert.index 用于 set 是合法的但 hash 必须对 — 用 BMVertElement 自带 hash
visited = set()
components = []
for v in bm.verts:
    if v not in visited:
        comp = flood_fill(v, len(components))
        components.append(comp)

print(f"  Found {len(components)} connected components")

# ---------- STEP 2: 评估每个分量的"形状各向异性" ----------
print("\n=== STEP 2: classify components by shape ===")

def component_anisotropy(comp_verts):
    """返回长宽比（max/min bbox 维度）。越大越细长。"""
    if not comp_verts:
        return 1.0, 0.0, []
    coords = [v.co for v in comp_verts]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    ranges = [max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)]
    sizes = sorted([r for r in ranges if r > 1e-6])
    if not sizes or sizes[0] < 1e-6:
        return 1.0, len(comp_verts), ranges
    return sizes[-1] / sizes[0], len(comp_verts), ranges

# 只评估前 N 大分量，避免处理百万个
sized = []
for i, comp in enumerate(components):
    aniso, n_v, ranges = component_anisotropy(comp)
    if n_v < 3:
        continue
    sized.append((i, aniso, n_v, ranges))

# 按顶点数排序
sized.sort(key=lambda x: -x[2])
print(f"  components with >= 3 verts: {len(sized)}")
print("  Top 10 components by vert count:")
for idx, aniso, n_v, ranges in sized[:10]:
    print(f"    comp {idx}: verts={n_v:5d}, aniso={aniso:5.2f}, bbox_range={tuple(round(r,4) for r in ranges)}")

# ---------- STEP 3: 识别并删除"细长尖刺" ----------
# 启发式: 顶点数 < 整个 mesh 1% 的分量 或 aniso > 8 的认为是尖刺
total_verts = len(bm.verts)
SPIKE_VERT_THRESHOLD = max(50, int(total_verts * 0.005))  # < 0.5% 的分量视为小
SPIKE_ANISO_THRESHOLD = 8.0

spike_verts = set()
main_verts = set()
reason_tags = []
for idx, aniso, n_v, ranges in sized:
    is_small = n_v < SPIKE_VERT_THRESHOLD
    is_aniso = aniso > SPIKE_ANISO_THRESHOLD
    comp = components[idx]
    if is_small or is_aniso:
        spike_verts.update(comp)
        tag = []
        if is_small:
            tag.append(f"small({n_v}<{SPIKE_VERT_THRESHOLD})")
        if is_aniso:
            tag.append(f"aniso({aniso:.1f}>{SPIKE_ANISO_THRESHOLD})")
        reason_tags.append((idx, n_v, aniso, ", ".join(tag)))
    else:
        main_verts.update(comp)

print(f"\n=== STEP 3: spike removal ===")
print(f"  total verts: {total_verts}")
print(f"  main_verts: {len(main_verts)} ({len(main_verts)*100/total_verts:.1f}%)")
print(f"  spike_verts: {len(spike_verts)} ({len(spike_verts)*100/total_verts:.1f}%)")
print(f"  thresholds: small<{SPIKE_VERT_THRESHOLD}, aniso>{SPIKE_ANISO_THRESHOLD}")
print(f"  classified spikes: {len(reason_tags)}")
for idx, n_v, aniso, tag in reason_tags[:5]:
    print(f"    comp {idx}: n={n_v}, {tag}")

# 删除尖刺对应的边和面
spike_edges = [e for e in bm.edges if any(v in spike_verts for v in e.verts)]
spike_faces = [f for f in bm.faces if any(v in spike_verts for v in f.verts)]
print(f"  removing {len(spike_faces)} faces, {len(spike_edges)} edges")

# 用 delete edges
bmesh.ops.delete(bm, geom=spike_faces, context='FACES_KEEP_BOUNDARY')
# 再清理孤立 verts
spike_v_list = list(spike_verts)
bmesh.ops.dissolve_verts(bm, verts=spike_v_list)

bm.to_mesh(hair.data)
hair.data.update()
print(f"  After spike removal: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 4: Make mesh manifold (fill any holes) ----------
print("\n=== STEP 4: ensure manifold ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary_count = sum(1 for e in bm.edges if not e.is_manifold)
print(f"  {boundary_count} boundary edges (holes)")
if boundary_count > 0:
    # Use built-in Fill Holes op which handles complex loops
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if not e.is_manifold])
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ---------- STEP 5: Heavy Laplacian smooth ----------
print("\n=== STEP 5: smooth factor 0.10 (x2) ===")
for it in range(2):
    bm = bmesh.new()
    bm.from_mesh(hair.data)
    bmesh.ops.smooth_vert(
        bm, verts=list(bm.verts), factor=0.10,
        use_axis_x=True, use_axis_y=True, use_axis_z=True,
    )
    bm.to_mesh(hair.data)
    bm.free()
    hair.data.update()
print(f"  After 2x smooth: dims={list(hair.dimensions)}")

# ---------- STEP 6: Solidify 1.5mm wall ----------
print("\n=== STEP 6: solidify 1.5mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.shade_smooth()
bpy.ops.object.modifier_add(type='SOLIDIFY')
mod_sol = hair.modifiers[-1]
mod_sol.thickness = 0.0015
mod_sol.offset = 0.0
mod_sol.use_even_offset = True
bpy.ops.object.modifier_apply(modifier=mod_sol.name)
hair.select_set(False)
print(f"  After solidify: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 7: Material (toon) ----------
print("\n=== STEP 7: toon material ===")
setup_toon_material(hair, color=(0.85, 0.85, 0.92), name="AFR_Hair_V9")

# ---------- STEP 8: Render ----------
print("\n=== STEP 8: render ===")
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True

# add sun
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

# Hide everything except hair (and sun/camera)
for o in bpy.data.objects:
    if o.type == "MESH" and o != hair:
        o.hide_render = True
        o.hide_viewport = True

cam = bpy.context.scene.camera
bb = []
for c in hair.bound_box:
    bb.append(hair.matrix_world @ Vector(c))
center = sum(bb, Vector((0,0,0))) / len(bb)
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
print(f"  center={center}, size={size}")

for view_name, off in [
    ("diag", (size*1.0, -size*1.0, size*0.4)),
    ("front", (0, -size*1.6, 0)),
    ("side", (size*1.6, 0, 0)),
]:
    cam.location = (center.x + off[0], center.y + off[1], center.z + off[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    out_path = os.path.join(OUT_DIR, f"hair_v9_{view_name}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  saved {out_path}")

# ---------- STEP 9: Save blend ----------
out_blend = os.path.join(OUT_DIR, "hair_anime_v9.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"\n=== SAVED {out_blend} ===")
print(f"  final verts: {len(hair.data.vertices)}")
print(f"  final dims: {list(hair.dimensions)}")
