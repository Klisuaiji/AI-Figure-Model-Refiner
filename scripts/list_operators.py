"""Install and inspect AI Figure Refiner operators."""
import bpy
import os
import sys

ADDON_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\addon\ai_figure_refiner"

# Add to addon path
if ADDON_DIR not in [p.__str__() for p in sys.path]:
    sys.path.append(os.path.dirname(ADDON_DIR))

# Try to enable
try:
    import ai_figure_refiner
    ai_figure_refiner.register()
    print("Addon registered OK")
except Exception as e:
    print(f"Register failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# List operators
print("\n=== AFR_OT_* operators ===")
afropts_full = []
for name in dir(bpy.types):
    if name.startswith("AFR_OT_"):
        cls = getattr(bpy.types, name)
        afropts_full.append((name, cls.bl_label, cls.bl_idname, getattr(cls, "bl_description", "")[:80]))

for n, lbl, bid, desc in afropts_full:
    print(f"  {n:50s} | {lbl:35s} | {bid:35s} | {desc}")

# List properties
print("\n=== Scene properties ===")
for p in dir(bpy.types.Scene):
    if p.startswith("afr_"):
        print(f"  Scene.{p}")
print("\n=== Object properties ===")
for p in dir(bpy.types.Object):
    if p.startswith("afr_"):
        print(f"  Object.{p}")
