"""Check actual state of the hair_anime.blend."""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow\hair_anime.blend")
hair = bpy.data.objects.get("part_2.001")
print(f"hair name: {hair.name}")
print(f"  location: {hair.location}")
print(f"  dimensions: {hair.dimensions}")
print(f"  bbox[0]: {hair.bound_box[0]}")
print(f"  bbox[6]: {hair.bound_box[6]}")
print(f"  verts: {len(hair.data.vertices)}")
print(f"  faces: {len(hair.data.polygons)}")
print(f"  modifiers: {[(m.name, m.type) for m in hair.modifiers]}")
# Sample some vertex positions
import random
random.seed(0)
sample_verts = random.sample(list(hair.data.vertices), 5)
print(f"  sample vertex positions (world):")
for v in sample_verts:
    world_co = hair.matrix_world @ v.co
    print(f"    {world_co}")
