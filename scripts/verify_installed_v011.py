"""Headless verification that the INSTALLED addon loads as V0.11 and exposes
the solver-free semi-automatic connector API."""
import sys, os
import bpy
import bmesh

ADDON = "D:/blender/5.2/scripts/addons/ai_figure_refiner"
ADDONS_DIR = os.path.dirname(ADDON)
if ADDONS_DIR not in sys.path:
    sys.path.insert(0, ADDONS_DIR)

import ai_figure_refiner as afr
from ai_figure_refiner.parts_ops import connectors

ok = True
ver = afr.bl_info.get("version")
print("installed version:", ver)
if tuple(ver) != (0, 11, 0):
    print("FAIL: expected (0,11,0)")
    ok = False

# create a throwaway scene/collection context
scene = bpy.context.scene
res = connectors.create_connector(
    scene, kind=connectors.KIND_ROUND, position=(0, 0, 0),
    direction=(0, 0, 1), diameter=5.0, depth=4.0, socket_wall_mm=1.2,
)
need = {"kind", "male", "female_socket", "female_cutter", "params"}
missing = need - set(res.keys())
print("result keys:", sorted(res.keys()))
if missing:
    print("FAIL: missing keys", missing)
    ok = False
if res.get("female_socket") is None:
    print("FAIL: female_socket is None")
    ok = False
if res.get("female_cutter") is not None:
    print("FAIL: non-legacy create_connector should not emit a cutter")
    ok = False

# manifold check on the socket
sock = res["female_socket"]
bm = bmesh.new()
bm.from_mesh(sock.data)
nonman = [e for e in bm.edges if not e.is_manifold]
print("socket verts=%d edges=%d nonmanifold=%d" % (
    len(bm.verts), len(bm.edges), len(nonman)))
bm.free()
if nonman:
    print("FAIL: socket is non-manifold")
    ok = False

print("== PASS ==" if ok else "== FAIL ==")
sys.exit(0 if ok else 1)
