"""Save the HAIR to a standalone .blend so we can process it in isolation."""
import bpy
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

# Delete all mesh objects EXCEPT part_2.001
hair = bpy.data.objects.get("part_2.001")
if hair is None:
    print("ERROR: part_2.001 not found")
    raise SystemExit(1)

for o in list(bpy.data.objects):
    if o is not hair and o.type == "MESH":
        bpy.data.objects.remove(o, do_unlink=True)
# Also remove orphaned meshes
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)

# Add a sun + camera if missing
if not any(o.type == "LIGHT" for o in bpy.data.objects):
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 4.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)
if not any(o.type == "CAMERA" for o in bpy.data.objects):
    bpy.ops.object.camera_add(location=(0, -3, 1))
    bpy.context.scene.camera = bpy.context.view_layer.objects.active

bpy.context.scene.world.use_nodes = True
bpy.context.scene.world.node_tree.nodes.clear()
bgn = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeBackground")
bgn.inputs["Color"].default_value = (0.4, 0.4, 0.42, 1.0)
bgn.inputs["Strength"].default_value = 0.6
out_node = bpy.context.scene.world.node_tree.nodes.new("ShaderNodeOutputWorld")
bpy.context.scene.world.node_tree.links.new(bgn.outputs["Background"], out_node.inputs["Surface"])
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.eevee.taa_render_samples = 32
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800
bpy.context.scene.render.film_transparent = True
bpy.context.scene.render.image_settings.color_mode = "RGBA"
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.context.scene.view_settings.view_transform = "Standard"

# Save
out = os.path.join(OUT_DIR, "hair_only.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"Saved {out}")
print(f"  hair verts: {len(hair.data.vertices)}")
print(f"  hair bbox: {list(hair.dimensions)}")
print(f"  objects: {[o.name for o in bpy.data.objects]}")
