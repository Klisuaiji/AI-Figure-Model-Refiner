"""Quick test: render only the doll with no other objects visible.
This is a focused test to verify the hide_render actually works."""
import bpy
import os
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\Qq203\Downloads\AI Figure Model Refiner\output\workflow_demo\intermediate_with_doll.blend")

# Find the doll
doll = bpy.data.objects.get("doll")
print(f"Found doll: {doll}")
print(f"  hide_render: {doll.hide_render}")
print(f"  materials: {[m.name for m in doll.data.materials]}")
print(f"  color_attrs: {list(doll.data.color_attributes.keys())}")
print(f"  render_color_index: {doll.data.color_attributes.render_color_index}")

# Try setting all other objects to hide, force update
for o in bpy.data.objects:
    o.hide_render = (o.name != "doll")
    o.hide_viewport = (o.name != "doll")

# Force a scene update
bpy.context.view_layer.update()

# Check which objects will render
visible_objs = [o for o in bpy.data.objects if not o.hide_render]
print(f"Visible objects: {[o.name for o in visible_objs]}")

# Add a sun light for proper rendering
bpy.context.scene.world.use_nodes = True
world_nodes = bpy.context.scene.world.node_tree.nodes
bg = world_nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.3, 0.3, 0.3, 1.0)
    bg.inputs["Strength"].default_value = 1.0

# Add a sun
if "Sun" not in bpy.data.objects:
    light_data = bpy.data.lights.new("Sun", type="SUN")
    light_data.energy = 5.0
    light_obj = bpy.data.objects.new("Sun", light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = (5, -5, 10)

# Setup render
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 16
bpy.context.scene.render.resolution_x = 600
bpy.context.scene.render.resolution_y = 600
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"

# Frame on doll
bb = [doll.matrix_world @ Vector(c) for c in doll.bound_box]
center = sum(bb, Vector((0, 0, 0))) / 8.0
size = max(max(p[i] for p in bb) - min(p[i] for p in bb) for i in range(3))
cam = bpy.context.scene.camera
cam.location = (center.x, center.y - size * 1.5, center.z)
direction = center - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 35

out = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\workflow_demo\test_doll_alone.png"
bpy.context.scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print(f"Saved {out}")
