"""V0.13 headless integration test:
- version / panels / ref-image uploader UI symbols
- MCP: get_reference_images, set_part_labels, label_parts vision guard
  (FRONT mandatory) — run through InProcessBackend inside Blender.
"""
import os
import struct
import sys
import zlib

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
if tuple(ver) != (0, 13, 0):
    print("FAIL: version"); ok = False

panels = {c.__name__ for c in afr._CLASSES if c.__name__.startswith("AFR_PT")}
expect = {"AFR_PT_Main", "AFR_PT_Tool_Split", "AFR_PT_Tool_Hair",
          "AFR_PT_Tool_Fabric", "AFR_PT_Tool_Figure", "AFR_PT_Tool_Print",
          "AFR_PT_Tool_Connector", "AFR_PT_Tool_Agent", "AFR_PT_Tool_Export"}
if expect - panels:
    print("FAIL missing panels:", expect - panels); ok = False
else:
    print("panels: OK", len(panels))


def make_png(path):
    """Minimal 2x2 RGBA PNG (pure stdlib)."""
    w = h = 2
    raw = b"".join(b"\x00" + b"\x80\x80\x80\xff" * w for _ in range(h))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


FRONT_PNG = os.path.join(REPO, "output", "_v013_front.png")
make_png(FRONT_PNG)

# --- MCP tools through InProcessBackend ----------------------------------
from ai_figure_refiner.mcp.backend import InProcessBackend
from ai_figure_refiner.mcp import tools as mcp_tools

backend = InProcessBackend()

# 1) get_reference_images before upload -> front missing
res = mcp_tools.get_reference_images(backend)
views = res.get("views", {})
print("[get_reference_images] before:", {k: v["loaded"] for k, v in views.items()},
      "front_present:", res.get("front_present"))
if res.get("front_present"):
    print("FAIL: front should be missing before upload"); ok = False

# 2) label_parts vision guard without FRONT -> must error
res = mcp_tools.label_parts(backend, object_name=None, method="vision")
print("[label_parts vision no-front]:", res)
if "error" not in res or "正面" not in res["error"]:
    print("FAIL: vision guard should reject missing FRONT"); ok = False

# 3) upload FRONT reference image via operator
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
fig = bpy.context.active_object
fig.name = "Fig"
bpy.context.scene.afr_source = fig.name
bpy.ops.afr.ref_load_image(view_name="FRONT", filepath=FRONT_PNG)
from ai_figure_refiner.reference import views as ref_views
slot = ref_views.get_view_slot(bpy.context.scene, "FRONT")
print("[ref_load_image] FRONT slot loaded:", bool(slot.image_path),
      "path:", os.path.basename(slot.image_path))
if not slot.image_path:
    print("FAIL: FRONT image not loaded"); ok = False

# 4) get_reference_images after upload -> front present
res = mcp_tools.get_reference_images(backend)
print("[get_reference_images] after: front_present:", res.get("front_present"),
      "ready:", res.get("ready_for_multimodal"))
if not res.get("front_present"):
    print("FAIL: front should be present after upload"); ok = False

# 5) label_parts vision with FRONT -> heuristics baseline + front_image
res = mcp_tools.label_parts(backend, object_name=fig.name, method="vision")
print("[label_parts vision with-front]: counts=", res.get("counts"),
      "front_image:", os.path.basename(res.get("front_image", "")))
if res.get("error") or "counts" not in res:
    print("FAIL: vision label should succeed with FRONT"); ok = False

# 6) set_part_labels write-back (simulate multimodal vision result)
labels = [0] * len(fig.data.vertices)
for i, v in enumerate(fig.data.vertices):
    labels[i] = 3 if v.co.z < 0.5 else 1  # lower= BODY, upper= HAIR
res = mcp_tools.set_part_labels(backend, object_name=fig.name, labels=labels)
print("[set_part_labels]:", res)
if res.get("error") or res.get("vertices") != len(fig.data.vertices):
    print("FAIL: set_part_labels"); ok = False

# 7) split_by_part still works on labeled mesh
r = bpy.ops.afr.split_by_part()
created = [o.name for o in bpy.data.objects if o.name.startswith("Fig_")]
print("[split_by_part]:", created)
if not created:
    print("FAIL: split created nothing"); ok = False

afr.unregister()
print("== PASS ==" if ok else "== FAIL ==")
sys.exit(0 if ok else 1)
