"""Headless test for V0.3 reference image system."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = os.path.join(ROOT, "addon")
sys.path.insert(0, ADDON)

import bpy
import bmesh
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.utils.script_path_add(ADDON)
except Exception:
    pass
import ai_figure_refiner
ai_figure_refiner.register()


# --- Build a small reference PNG (solid color) so we can test loading ---
def _make_test_png(path, w=64, h=64, rgb=(255, 0, 0)):
    """Create a minimal PNG without PIL/numpy (uses struct + zlib)."""
    import struct
    import zlib
    r, g, b = rgb
    raw = b""
    for y in range(h):
        raw += b"\x00"  # filter byte
        for x in range(w):
            raw += bytes((r, g, b))
    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data +
                struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit RGB
    idat = zlib.compress(raw, 9)
    with open(path, "wb") as f:
        f.write(sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


from ai_figure_refiner.reference import views as ref_views


def run():
    out_dir = os.path.join(ROOT, "output")
    os.makedirs(out_dir, exist_ok=True)
    results = []

    # --- Test 1: ensure_ref_state creates 4 slots -----------------------
    sc = bpy.context.scene
    ref_views.ensure_ref_state(sc)
    names = [v.name for v in sc.afr_ref_views]
    results.append({"test": "ensure_ref_state", "slots": names})
    assert set(names) == set(ref_views.VIEW_NAMES), names

    # --- Test 2: create 4 cameras --------------------------------------
    for name in ref_views.VIEW_NAMES:
        ref_views.get_or_create_camera(sc, name)
    cam_names = [o.name for o in bpy.data.objects if o.type == "CAMERA" and o.name.startswith("AFR_RefCam_")]
    results.append({"test": "create_cameras", "cameras": cam_names})
    assert len(cam_names) == 4

    # --- Test 3: align cameras to bbox of a cube -----------------------
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 1.0))
    cube = bpy.context.active_object
    cube.name = "RefCube"
    for name in ref_views.VIEW_NAMES:
        ref_views.align_camera_to_bbox(sc, name, cube)
    bpy.context.view_layer.update()
    cam_locs = {o.name: list(o.matrix_world.translation)
                    for o in bpy.data.objects
                    if o.type == "CAMERA" and o.name.startswith("AFR_RefCam_")}
    results.append({"test": "align_cameras_to_bbox", "cam_locs": cam_locs})
    for nm, loc in cam_locs.items():
        d = (Vector(loc) - Vector((0, 0, 1))).length
        assert d > 1.0, "%s too close: %s" % (nm, d)
    # additionally verify they MOVED from the preset (preset FRONT cam at (0,-3,0))
    # after align to bbox centered at (0,0,1), FRONT cam should NOT be at (0,-3,0).
    moved = {nm: loc for nm, loc in cam_locs.items()}
    # build preset positions
    presets = {"AFR_RefCam_FRONT": [0, -3, 0],
               "AFR_RefCam_BACK":  [0,  3, 0],
               "AFR_RefCam_LEFT":  [-3, 0, 0],
               "AFR_RefCam_RIGHT": [3,  0, 0]}
    for nm, preset in presets.items():
        actual = moved.get(nm)
        if actual is None:
            continue
        d_to_preset = (Vector(actual) - Vector(preset)).length
        assert d_to_preset > 0.5, "%s didn't move from preset (still %s)" % (nm, actual)

    # --- Test 4: load test PNGs into each slot --------------------------
    paths = {}
    for n, color in zip(ref_views.VIEW_NAMES, [(255,0,0), (0,255,0), (0,0,255), (255,255,0)]):
        p = os.path.join(out_dir, "ref_%s.png" % n)
        _make_test_png(p, w=128, h=128, rgb=color)
        paths[n] = p
        img = ref_views.load_reference_image(sc, n, p)
        assert img is not None
        assert img.size[0] == 128 and img.size[1] == 128
    # verify the image is attached as background of each camera
    bgs = {n: [bi.image.name if bi.image else None
               for bi in bpy.data.objects["AFR_RefCam_" + n].data.background_images]
           for n in ref_views.VIEW_NAMES}
    results.append({"test": "load_images", "backgrounds": bgs})
    for n in ref_views.VIEW_NAMES:
        assert bgs[n] == ["AFR_RefImg_" + n], bgs[n]

    # --- Test 5: silhouette edge count for the cube from FRONT camera --
    scn_cam = bpy.data.objects["AFR_RefCam_FRONT"]
    n_edges = ref_views.silhouette_edge_count(cube, scn_cam)
    results.append({"test": "silhouette_edges_front", "edges": n_edges})
    assert n_edges > 0

    # --- Test 6: project outline returns points -------------------------
    pts = ref_views.project_outline(cube, scn_cam)
    results.append({"test": "project_outline", "points": len(pts)})
    assert len(pts) > 0

    # --- Test 7: clear one image ---------------------------------------
    ref_views.detach_background(bpy.data.objects["AFR_RefCam_FRONT"])
    bg_after = [bi.image for bi in bpy.data.objects["AFR_RefCam_FRONT"].data.background_images]
    results.append({"test": "clear_image", "backgrounds": bg_after})
    assert len(bg_after) == 0

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("== PASS ==")


run()