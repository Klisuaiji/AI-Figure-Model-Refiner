# -*- coding: utf-8 -*-
"""
Technical Feasibility Audit — runs inside Blender (headless).
Reports Blender/Python versions, available 3rd-party modules, 3MF/print/mesh
operator surface, 3MF data types, and enabled add-ons. Dumps JSON + prints a
human-readable summary. NEVER assume an API exists — verify it here.
"""
import os
import sys
import json
import traceback

INFO = {}

import bpy  # noqa: E402

INFO["blender"] = {
    "version": list(bpy.app.version),
    "version_string": bpy.app.version_string,
    "build_hash": getattr(bpy.app, "build_hash", None),
    "background": bool(bpy.app.background),
    "binary_path": bpy.app.binary_path,
}

INFO["python"] = {
    "version": sys.version,
    "executable": sys.executable,
}

# ---- 3rd-party module availability -----------------------------------------
MODULES = [
    "numpy", "scipy", "PIL", "cv2", "trimesh", "open3d",
    "onnxruntime", "sklearn", "mathutils", "bmesh", "gpu",
    "gpu_extras", "requests", "scipy",
]
INFO["modules"] = {}
for m in MODULES:
    try:
        mod = __import__(m)
        INFO["modules"][m] = {
            "available": True,
            "version": getattr(mod, "__version__", "unknown"),
        }
    except Exception as e:
        INFO["modules"][m] = {"available": False, "error": str(e)[:200]}

# ---- walk the entire operator surface --------------------------------------
def collect_ops():
    found = []
    try:
        for mod_name in dir(bpy.ops):
            if mod_name.startswith("_"):
                continue
            mod = getattr(bpy.ops, mod_name)
            for op_name in dir(mod):
                if op_name.startswith("_"):
                    continue
                found.append("%s.%s" % (mod_name, op_name))
    except Exception as e:
        found = ["ERROR: " + str(e)]
    return found

all_ops = collect_ops()
KEYWORDS = [
    "threemf", "3mf", "print", "mesh", "export", "import",
    "remesh", "solidify", "boolean", "separate", "shrinkwrap",
    "voxel", "convex", "decimate", "smooth", "normals", "weights",
]
INFO["ops_matching"] = {}
for kw in KEYWORDS:
    INFO["ops_matching"][kw] = [o for o in all_ops if kw in o.lower()]

# ---- 3MF data types --------------------------------------------------------
INFO["types_3mf"] = {
    t: hasattr(bpy.types, t)
    for t in [
        "ThreemfExportSettings", "ThreemfImportSettings",
        "WM_OT_threemf_export", "WM_OT_threemf_import",
        "Export3MF", "Import3MF",
    ]
}

# ---- enabled add-ons -------------------------------------------------------
enabled = list(bpy.context.preferences.addons.keys())
RELEVANT = ["mcp", "print", "mesh", "import", "export", "3d", "three", "tool"]
INFO["addons"] = {
    "total": len(enabled),
    "relevant": sorted([a for a in enabled if any(k in a.lower() for k in RELEVANT)]),
}

# ---- scene stats -----------------------------------------------------------
INFO["scene"] = {
    "objects": len(bpy.data.objects),
    "meshes": len(bpy.data.meshes),
}

# ---- output ----------------------------------------------------------------
def _sanitize(o):
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    return o


out_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
)
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "audit_blender_env.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(_sanitize(INFO), f, ensure_ascii=False, indent=2)

print("=" * 70)
print("BLENDER ENV AUDIT  (%s)" % INFO["blender"]["version_string"])
print("=" * 70)
print("Python :", INFO["python"]["version"].splitlines()[0])
print("Binary :", INFO["blender"]["binary_path"])
print("-" * 70)
print("MODULES:")
for k, v in INFO["modules"].items():
    if v.get("available"):
        print("  [OK]   %-12s %s" % (k, v["version"]))
    else:
        print("  [MISS] %-12s %s" % (k, v.get("error", "")[:60]))
print("-" * 70)
print("3MF ops:", INFO["ops_matching"].get("threemf"))
print("3mf types:", INFO["types_3mf"])
print("Addons total:", INFO["addons"]["total"])
print("Relevant addons:", INFO["addons"]["relevant"])
print("Output JSON:", out_path)
print("=" * 70)
