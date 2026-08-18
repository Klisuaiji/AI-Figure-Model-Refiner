"""Render the anime-ified figure with all parts together."""
import bpy
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT_DIR, "figure_anime.blend"))

# Set up sun + world
bpy.context.scene.world.use_nodes = True
bpy.context.scene.world.node_tree.nodes.clear()
bgn = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeBackground")
bgn.inputs["Color"].default_value = (0.4, 0.4, 0.42, 1.0)
bgn.inputs["Strength"].default_value = 0.5
out_node = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeOutputWorld")
bpy.context.scene.world.node_tree.links.new(bgn.outputs["Background"], out_node.inputs["Surface"])

# Add sun light
if not any(o.type == "LIGHT" for o in bpy.data.objects):
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 4.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)
# Add camera
if not any(o.type == "CAMERA" for o in bpy.data.objects):
    bpy.ops.object.camera_add(location=(0, -3, 1))
    bpy.context.scene.camera = bpy.context.view_layer.objects.active

bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.context.scene.view_settings.view_transform = "Standard"

# Get all figure meshes
all_mesh = [o for o in bpy.data.objects if o.type == "MESH"]
print(f"Mesh objects: {len(all_mesh)}")
for o in all_mesh:
    print(f"  {o.name}: loc={list(o.location)}, dim={list(o.dimensions)}, v={len(o.data.vertices)}")

# Frame on all
bb_all = []
for o in all_mesh:
    for c in o.bound_box:
        bb_all.append(o.matrix_world @ Vector(c))
center = sum(bb_all, Vector((0, 0, 0))) / len(bb_all)
size = max(max(p[i] for p in bb_all) - min(p[i] for p in bb_all) for i in range(3))
print(f"\nFrame: center={center}, size={size}")

cam = bpy.context.scene.camera
for view_name, view_offset in [
    ("diag", (size * 1.0, -size * 1.0, size * 0.5)),
    ("front", (0, -size * 1.6, 0)),
    ("back", (0, size * 1.6, 0)),
    ("side", (size * 1.6, 0, 0)),
]:
    cam.location = (center.x + view_offset[0],
                    center.y + view_offset[1],
                    center.z + view_offset[2])
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()
    bpy.context.scene.render.filepath = os.path.join(OUT_DIR, f"figure_anime_{view_name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"  saved figure_anime_{view_name}.png")
