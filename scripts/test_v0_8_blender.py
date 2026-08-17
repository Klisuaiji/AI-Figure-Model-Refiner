"""Blender-side sanity check for V0.8 (under blender --background)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "addon"))

import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)

import ai_figure_refiner
ai_figure_refiner.register()


# 1. operator count
op_count = sum(1 for c in dir(bpy.types) if c.startswith("AFR_OT_"))
assert op_count >= 35, "expected >= 35 operators, got %d" % op_count

# 2. bl_options REGISTER/UNDO check on every ImportHelper/ExportHelper subclass
import inspect
from bpy_extras.io_utils import ImportHelper, ExportHelper
missing = []
total = 0
for name, obj in inspect.getmembers(bpy.types):
    if name.startswith("AFR_OT_") and issubclass(obj, (ImportHelper, ExportHelper)):
        total += 1
        opts = getattr(obj, "bl_options", set())
        if "REGISTER" not in opts or "UNDO" not in opts:
            missing.append(name)
assert not missing, "missing REGISTER/UNDO: %s" % missing

# 3. version check
assert bpy.context.scene.afr_print is not None
assert bpy.context.scene.afr_log is not None

print("== V0.8 Blender sanity PASS ==")
print("  operator_count =", op_count)
print("  file_dialog_operators =", total)
print("  missing_bl_options =", missing)
print("  afr_print property =", bpy.context.scene.afr_print.nozzle_mm)
print("  afr_log property =", "OK")
print("  bl_info version =", ai_figure_refiner.bl_info["version"])