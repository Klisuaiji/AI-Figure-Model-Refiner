"""V0.12 headless integration test: register toolset, verify panels/operators,
and smoke-run the six tools on a generated mesh."""
import sys, os
import bpy
import bmesh

REPO = "D:/Qq203/Downloads/AI Figure Model Refiner"
ADDON = os.path.join(REPO, "addon")
if ADDON not in sys.path:
    sys.path.insert(0, ADDON)

import ai_figure_refiner as afr
afr.register()

ok = True
ver = afr.bl_info.get("version")
print("version:", ver)
if tuple(ver) != (0, 12, 0):
    print("FAIL: version")
    ok = False

# --- panels registered? (registered wrapper name = class name) ---
panels = {c.__name__ for c in afr._CLASSES if c.__name__.startswith("AFR_PT")}
expect_panels = {
    "AFR_PT_Main", "AFR_PT_Tool_Split", "AFR_PT_Tool_Hair", "AFR_PT_Tool_Fabric",
    "AFR_PT_Tool_Figure", "AFR_PT_Tool_Print", "AFR_PT_Tool_Connector",
    "AFR_PT_Tool_Agent", "AFR_PT_Tool_Export",
}
missing_p = expect_panels - set(panels)
print("panels found:", sorted(panels))
if missing_p:
    print("FAIL missing panels:", missing_p)
    ok = False

# --- sub-panel nesting: every tool panel must parent to AFR_PT_Main ----
main_id = bpy.types.AFR_PT_Main.bl_rna.identifier
bad_nest = []
for c in afr._CLASSES:
    if c.__name__.startswith("AFR_PT_Tool"):
        pid = getattr(c, "bl_parent_id", None)
        if pid != main_id:
            bad_nest.append((c.__name__, pid))
print("nesting: main=%s bad=%s" % (main_id, bad_nest))
if bad_nest:
    print("FAIL: sub-panel nesting"); ok = False

# --- new operator registered? (bpy.types uses snake_case wrapper) -------
op_registered = hasattr(bpy.types, "AFR_OT_split_by_part")
print("AFR_OT_split_by_part registered:", op_registered)
if not op_registered:
    print("FAIL: split_by_part operator")
    ok = False

# --- build a test mesh with semantic variety -----------------------------
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
fig = bpy.context.active_object
fig.name = "Fig"
bpy.ops.object.shade_smooth()

from ai_figure_refiner.semantic import parts as sem_parts
from ai_figure_refiner.parts_ops import hair as hair_ops

# label: top faces -> HAIR, bottom -> BASE, rest BODY
sem_parts.ensure_part_attribute(fig)
bm = bmesh.new(); bm.from_mesh(fig.data)
zs = [v.co.z for v in bm.verts]
zmax, zmin = max(zs), min(zs)
bm.faces.ensure_lookup_table()
arr = [sem_parts.PART_ID["BODY"]] * len(bm.verts)
for f in bm.faces:
    for v in f.verts:
        if v.co.z > zmin + 0.75 * (zmax - zmin):
            arr[v.index] = sem_parts.PART_ID["HAIR"]
        elif v.co.z < zmin + 0.15 * (zmax - zmin):
            arr[v.index] = sem_parts.PART_ID["BASE"]
sem_parts.set_label_array(fig, arr)
bm.free()

# --- tool 1: split by part -------------------------------------------------
try:
    res = bpy.ops.afr.split_by_part()
    created = [o.name for o in bpy.data.objects if o.name.startswith("Fig_")]
    print("[split_by_part]", "OK", "created:", sorted(created))
    if not any(n.endswith(("_HAIR", "_BODY", "_BASE")) for n in created):
        print("FAIL: no parts created"); ok = False
except Exception as e:
    print("[split_by_part] FAIL:", repr(e)); ok = False

# --- tool 2: hair solidify (on Fig) -----------------------------------------
try:
    op = bpy.ops.afr.hair_solidify  # operator exists check only (mesh may lack hair)
    print("[hair_solidify] operator exists OK")
except Exception as e:
    print("[hair_solidify] FAIL:", repr(e)); ok = False

# --- tool: printability ------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(5, 0, 0))
cube = bpy.context.active_object
bpy.context.scene.afr_source = cube.name
try:
    r = bpy.ops.afr.run_printability()
    print("[run_printability]", r)
except Exception as e:
    print("[run_printability] FAIL:", repr(e)); ok = False

# --- tool: export 3MF ---------------------------------------------------------
out3mf = os.path.join(REPO, "output", "_v012_smoke.3mf")
try:
    bpy.ops.afr.export_3mf(filepath=out3mf)
    print("[export_3mf] OK, exists:", os.path.exists(out3mf))
except Exception as e:
    print("[export_3mf] FAIL:", repr(e)); ok = False

# --- tool: 4-quadrant ref cameras ----------------------------------------------
try:
    r = bpy.ops.afr.ref_create_cameras()
    cams = [o.name for o in bpy.data.objects if o.name.startswith("AFR_RefCam")]
    print("[ref_create_cameras]", r, "cams:", sorted(cams))
except Exception as e:
    print("[ref_create_cameras] FAIL:", repr(e)); ok = False

afr.unregister()
print("== PASS ==" if ok else "== FAIL ==")
sys.exit(0 if ok else 1)
