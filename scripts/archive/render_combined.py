"""Render combined views: full scene, all-parts only, Mesh_0 only, Mesh_0.001 only."""
import bpy
from mathutils import Vector
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\unnamed_inspect"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.context.scene.view_settings.view_transform = "Standard"

# Check for material slots
print("=== Materials per object ===")
for o in bpy.data.objects:
    if o.type == "MESH" and o.data.materials:
        mats = []
        for m in o.data.materials:
            if m:
                # Try to get a vertex color count and material color
                try:
                    c = m.diffuse_color
                    mats.append(f"{m.name} (rgb=({c[0]:.2f},{c[1]:.2f},{c[2]:.2f}))")
                except Exception:
                    mats.append(m.name)
        print(f"  {o.name}: {mats}")

# Check vertex colors per object
print("\n=== Vertex colors ===")
for o in bpy.data.objects:
    if o.type == "MESH":
        for cl in o.data.color_attributes:
            print(f"  {o.name}.{cl.name}: domain={cl.domain}, data_type={cl.data_type}")


def frame_on(center, size, lens=50, angle="diag"):
    cam = bpy.context.scene.camera
    if angle == "diag":
        cam.location = (center.x + size, center.y - size, center.z + size * 0.7)
    elif angle == "front":
        cam.location = (center.x, center.y - size * 1.5, center.z)
    elif angle == "back":
        cam.location = (center.x, center.y + size * 1.5, center.z)
    elif angle == "top":
        cam.location = (center.x, center.y, center.z + size * 1.5)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    bpy.context.view_layer.update()


# Ensure we have a camera
if bpy.context.scene.camera is None or bpy.context.scene.camera.name not in {"Camera"}:
    bpy.context.scene.camera = bpy.data.objects.get("Camera")

# Frame on the part_X.001 cluster (all at x=1.47)
parts = [o for o in bpy.data.objects if o.name.startswith("part_")]
all_corners = []
for o in parts:
    for corner in o.bound_box:
        all_corners.append(o.matrix_world @ Vector(corner))
if all_corners:
    cx = sum(c.x for c in all_corners) / len(all_corners)
    cy = sum(c.y for c in all_corners) / len(all_corners)
    cz = sum(c.z for c in all_corners) / len(all_corners)
    center = Vector((cx, cy, cz))
    max_size = max(
        max(p[i] for p in all_corners) - min(p[i] for p in all_corners)
        for i in range(3)
    )
    print(f"\nparts cluster center={center}, size={max_size:.2f}")

    # Hide everything except parts
    for o in bpy.data.objects:
        o.hide_render = o not in parts

    # Three views: front, back, side
    for view_name, angle in [("front", "front"), ("back", "back"), ("diag", "diag")]:
        frame_on(center, max_size * 1.0, lens=35, angle=angle)
        bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"parts_cluster_{view_name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Wrote parts_cluster_{view_name}.png")

# Now Mesh_0 alone
mesh0 = bpy.data.objects.get("Mesh_0")
if mesh0:
    bb = [mesh0.matrix_world @ Vector(c) for c in mesh0.bound_box]
    c = sum(bb, Vector((0, 0, 0))) / 8.0
    s = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
    for o in bpy.data.objects:
        o.hide_render = (o is not mesh0)
    for view_name, angle in [("front", "front"), ("back", "back"), ("diag", "diag")]:
        frame_on(c, s * 1.0, lens=35, angle=angle)
        bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"mesh0_{view_name}.png")
        bpy.ops.render.render(write_still=True)

# Now Mesh_0.001 alone
mesh1 = bpy.data.objects.get("Mesh_0.001")
if mesh1:
    bb = [mesh1.matrix_world @ Vector(c) for c in mesh1.bound_box]
    c = sum(bb, Vector((0, 0, 0))) / 8.0
    s = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
    for o in bpy.data.objects:
        o.hide_render = (o is not mesh1)
    for view_name, angle in [("front", "front"), ("back", "back"), ("diag", "diag")]:
        frame_on(c, s * 1.0, lens=35, angle=angle)
        bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"mesh1_{view_name}.png")
        bpy.ops.render.render(write_still=True)

print("\nAll done")
