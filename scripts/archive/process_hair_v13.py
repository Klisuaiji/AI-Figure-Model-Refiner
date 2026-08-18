"""V13 - V4 流程 + 删高 aniso 的小连通分量（spike 整体）。

V4 后刺是 1D 细管——单面 thinness 不一定高，但整个 component 的
bbox 长宽比 (aniso) 极高 (>10)。

策略:
  1. decimate 0.04 (V4 流程)
  2. holes fill
  3. 找 connected component：max_volume comp = 主体
  4. 对其他 comps:
     - bbox_aniso > 8 OR
     - bbox 体积 < 主体体积 5%
     视为 spike，删掉
  5. re-fill holes
  6. light smooth
  7. solidify
  8. toon
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
print(f"--- V13: V4 + small component removal ---")
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

# ---------- STEP 3: find connected components ----------
print("\n=== STEP 3: find components ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bm.edges.ensure_lookup_table()
bm.verts.ensure_lookup_table()

# BFS for connected components (face adjacency via shared edges)
visited = set()
components = []
for f in bm.faces:
    if f in visited:
        continue
    stack = [f]
    comp_faces = set()
    while stack:
        x = stack.pop()
        if x in visited:
            continue
        visited.add(x)
        comp_faces.add(x)
        for e in x.edges:
            for other_f in e.link_faces:
                if other_f not in visited:
                    stack.append(other_f)
    components.append(comp_faces)

components.sort(key=lambda c: -len(c))
print(f"  total components: {len(components)}")
for i, c in enumerate(components[:10]):
    verts_in = set()
    for f in c:
        for v in f.verts:
            verts_in.add(v)
    coords = [v.co for v in verts_in]
    if not coords:
        continue
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    bbox = (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    bbox_valid = [b for b in bbox if b > 1e-4]
    aniso = max(bbox) / max(min(bbox_valid) if bbox_valid else 0.001, 0.001)
    vol = bbox[0] * bbox[1] * bbox[2]
    print(f"    comp[{i}]: faces={len(c):5d}, verts={len(verts_in):5d}, "
          f"bbox=({bbox[0]:.3f},{bbox[1]:.3f},{bbox[2]:.3f}), aniso={aniso:.1f}, vol={vol:.4f}")

# ---------- STEP 4: delete spike components ----------
# Heuristics:
#   - the LARGEST component is main body (always keep)
#   - any comp with bbox_aniso > 6 OR volume < main_volume*0.005 = spike
main_comp = components[0]
main_verts = set()
for f in main_comp:
    for v in f.verts:
        main_verts.add(v)
main_coords = [v.co for v in main_verts]
mx = [c.x for c in main_coords]
my = [c.y for c in main_coords]
mz = [c.z for c in main_coords]
main_bbox = (max(mx)-min(mx), max(my)-min(my), max(mz)-min(mz))
main_volume = main_bbox[0] * main_bbox[1] * main_bbox[2]
print(f"\n  main: {len(main_comp)} faces, vol={main_volume:.4f}, bbox={main_bbox}")

SPIKE_ANISO = 6.0
SPIKE_VOL_FRAC = 0.005
spike_faces = set()
spike_tags = []
for i, c in enumerate(components[1:], 1):
    verts_in = set()
    for f in c:
        for v in f.verts:
            verts_in.add(v)
    coords = [v.co for v in verts_in]
    if not coords:
        continue
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    bbox = (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    bbox_valid = [b for b in bbox if b > 1e-4]
    aniso = max(bbox) / max(min(bbox_valid) if bbox_valid else 0.001, 0.001)
    vol = bbox[0] * bbox[1] * bbox[2]
    is_aniso = aniso > SPIKE_ANISO
    is_small = vol < main_volume * SPIKE_VOL_FRAC
    if is_aniso or is_small:
        spike_faces.update(c)
        spike_tags.append((i, len(c), aniso, vol, is_aniso, is_small))

print(f"\n  classified spikes: {len(spike_tags)} components")
for i, n, an, v, ia, iv in spike_tags:
    print(f"    comp[{i}]: faces={n}, aniso={an:.1f}, vol={v:.4f}, aniso={ia}, small={iv}")

print(f"\n=== STEP 4: delete spike faces ===")
bmesh.ops.delete(bm, geom=list(spike_faces), context='FACES_KEEP_BOUNDARY')
bm.verts.ensure_lookup_table()
orphan_verts = [v for v in bm.verts if len(v.link_faces) == 0]
print(f"  orphan verts to dissolve: {len(orphan_verts)}")
if orphan_verts:
    bmesh.ops.dissolve_verts(bm, verts=orphan_verts)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After spike delete: {len(hair.data.vertices)} verts, dims={list(hair.dimensions)}")

# ---------- STEP 5: re-fill holes ----------
print("\n=== STEP 5: re-fill holes ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()
print(f"  After fill: {len(hair.data.vertices)} verts")

# ---------- STEP 6: light smooth ----------
print("\n=== STEP 6: smooth factor 0.10 x1 ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.10,
                      use_axis_x=True, use_axis_y=True, use_axis_z=True)
bm.to_mesh(hair.data)
bm.free()
hair.data.update()

# ---------- STEP 7: re-fill ----------
print("\n=== STEP 7: re-fill after smooth ===")
bm = bmesh.new()
bm.from_mesh(hair.data)
boundary = [e for e in bm.edges if not e.is_manifold]
print(f"  boundary edges: {len(boundary)}")
if boundary:
    bmesh.ops.holes_fill(bm, edges=boundary)
bm.to_mesh(hair.data)
hair.data.update()

# ---------- STEP 8: solidify 2mm ----------
print("\n=== STEP 8: solidify 2mm ===")
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

# ---------- STEP 9: toon material ----------
print("\n=== STEP 9: toon material ===")
mat = bpy.data.materials.new("AFR_Hair_V13")
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

# ---------- STEP 10: render ----------
print("\n=== STEP 10: render ===")
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
    out_path = os.path.join(OUT_DIR, f"hair_v13_{view_name}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  saved {out_path}")

out_blend = os.path.join(OUT_DIR, "hair_anime_v13.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f"\n=== SAVED {out_blend} ===")
print(f"  final verts: {len(hair.data.vertices)}")
print(f"  final dims: {list(hair.dimensions)}")
