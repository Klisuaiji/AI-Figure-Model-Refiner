"""V11 - 真·笔触化：识别 + 切除细刺尾巴 + 体素重网格 + toon。

诊断结果：
  comp[0]: 190,955 顶点，半径 0.29 椭球 + 一个尾巴延伸到 x=-0.295
  comp[1]: 1,128 顶点（小辫子，单独 component）
  comp[2,3]: 单点游离

策略：
  1. 保留 comp[0] 椭球 + comp[1] 小辫子
  2. 删掉 comp[0] 中 x < -0.20 的 vertex（尾部细刺）
  3. Voxel Remesh 0.025m 把剩下的细三角形全消除
  4. Smooth factor 0.10 (Laplacian)
  5. Solidify 2mm
  6. Toon material
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
print(f"--- V11: tail cut + voxel remesh ---")
print(f"  Hair: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 1: Connected components ----------
bm = bmesh.new()
bm.from_mesh(hair.data)
visited = set()
components = []
for v in bm.verts:
    if v in visited: continue
    stack = [v]; comp = set()
    while stack:
        x = stack.pop()
        if x in visited: continue
        visited.add(x); comp.add(x)
        for e in x.link_edges:
            o = e.other_vert(x)
            if o not in visited: stack.append(o)
    components.append(comp)
components.sort(key=len, reverse=True)
print(f"\n  {len(components)} components: " +
      ", ".join(f"c{i}={len(c)}" for i, c in enumerate(components)))

main_comp = components[0]
small_braid = components[1] if len(components) > 1 else set()

# ---------- STEP 2: cut tail of main_comp ----------
# Find centroid of main_comp's "core" (excluding x < -0.20)
core_verts = [v for v in main_comp if v.co.x > -0.20]
tail_verts = [v for v in main_comp if v.co.x <= -0.20]
print(f"\n=== STEP 2: cut tail (x <= -0.20) ===")
print(f"  main core: {len(core_verts)}, main tail: {len(tail_verts)}")

# delete faces touching tail verts
tail_faces = [f for f in bm.faces if any(v in tail_verts for v in f.verts)]
print(f"  tail faces: {len(tail_faces)}")
bmesh.ops.delete(bm, geom=tail_faces, context='FACES_KEEP_BOUNDARY')
# dissolve tail verts
bm.verts.ensure_lookup_table()
remaining_tail = [v for v in tail_verts if v in bm.verts and len(v.link_faces) == 0]
print(f"  dissolve {len(remaining_tail)} orphan tail verts")
if remaining_tail:
    bmesh.ops.dissolve_verts(bm, verts=remaining_tail)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After cut: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# Fill holes
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges to fill: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()

# ---------- STEP 3: reattach the braid comp[1] ----------
# comp[1] is separate (1,128 verts), currently still in bm.faces
# Check if it's still there
print(f"\n=== STEP 3: braid component handling ===")
# Recount components after tail cut
bm = bmesh.new()
bm.from_mesh(hair.data)
visited = set(); comps_new = []
for v in bm.verts:
    if v in visited: continue
    stack = [v]; comp = set()
    while stack:
        x = stack.pop()
        if x in visited: continue
        visited.add(x); comp.add(x)
        for e in x.link_edges:
            o = e.other_vert(x)
            if o not in visited: stack.append(o)
    comps_new.append(comp)
comps_new.sort(key=len, reverse=True)
print(f"  components after tail cut: {len(comps_new)}")
for i, c in enumerate(comps_new[:5]):
    print(f"    comp{i} = {len(c)} verts")
bm.to_mesh(hair.data)
hair.data.update()

# ---------- STEP 4: Voxel Remesh 25mm (kill all spaghetti triangles) ----------
# Voxel size 2.5cm is enough to merge thin spikes into a block
print(f"\n=== STEP 4: voxel remesh (25mm) ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.shade_smooth()
# Add remesh modifier
bpy.ops.object.modifier_add(type='REMESH')
rem = hair.modifiers["Remesh"]
rem.mode = 'VOXEL'
rem.voxel_size = 0.025
bpy.ops.object.modifier_apply(modifier="Remesh")
hair.select_set(False)
print(f"  After remesh: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 5: Fill holes from remesh ----------
print("\n=== STEP 5: re-fill after remesh ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ---------- STEP 6: Light Laplacian smooth (factor 0.08 x1) ----------
print("\n=== STEP 6: smooth factor 0.08 x1 ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.08,
                      use_axis_x=True, use_axis_y=True, use_axis_z=True)
bm.to_mesh(hair.data)
bm.free()
hair.data.update()
print(f"  After smooth: dims={list(hair.dimensions)}")

# ---------- STEP 7: Solidify 2mm ----------
print("\n=== STEP 7: solidify 2mm ===")
bpy.context.view_layer.objects.active = hair
hair.select_set(True)
bpy.ops.object.modifier_add(type='SOLIDIFY')
sol = hair.modifiers[-1]
sol.thickness = 0.002
sol.offset = 0.0
sol.use_even_offset = True
bpy.ops.object.modifier_apply(modifier=sol.name)
hair.select_set(False)
print(f"  After solidify: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 8: Toon material ----------
print("\n=== STEP 8: toon material ===")
mat = bpy.data.materials.new("AFR_Hair_V11")
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

# ---------- STEP 9: Render ----------
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
    out_path = os.path.join(OUT_DIR, f"hair_v11_{view_name}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  saved {out_path}")

out_blend = os.path.join(OUT_DIR, "hair_anime_v11.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"\n=== SAVED {out_blend} ===")
print(f"  final verts: {len(hair.data.vertices)}")
print(f"  final dims: {list(hair.dimensions)}")
