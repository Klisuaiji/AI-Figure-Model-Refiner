"""Compare dimensions of hair_only.blend vs hair_anime.blend."""
import bpy
for path in [r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow\hair_only.blend",
             r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow\hair_anime.blend"]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    hair = bpy.data.objects.get("part_2.001")
    print(f"{path.split('/')[-1]}:")
    print(f"  verts: {len(hair.data.vertices)}")
    print(f"  faces: {len(hair.data.polygons)}")
    print(f"  dimensions: {hair.dimensions}")
    print(f"  bbox[0]: {hair.bound_box[0]}")
    print(f"  bbox[6]: {hair.bound_box[6]}")
