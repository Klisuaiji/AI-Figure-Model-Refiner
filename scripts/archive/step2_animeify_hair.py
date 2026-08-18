"""ANIME-ify + 3D print optimization:
- Shade Smooth + Subdivision Surface (Catmull-Clark) for anime hair look
- Solidify (1.5mm) for 3D-print wall thickness
- No decimation (preserves detail)
"""
import bpy
import os
from mathutils import Vector

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"
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

# Add sun light
if "Sun" not in bpy.data.objects:
    ld = bpy.data.lights.new("Sun", type="SUN")
    ld.energy = 4.0
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = (3, -3, 5)
bpy.context.scene.world.use_nodes = True
bgn = bpy.context.scene.world.node_tree.nodes.get("Background")
if bgn:
    bgn.inputs["Color"].default_value = (0.4, 0.4, 0.42, 1.0)
    bgn.inputs["Strength"].default_value = 0.6


def frame_on(objs, view="diag", extra=1.5):
    cam = bpy.context.scene.camera
    if cam is None or cam.name == "Camera":
        bpy.ops.object.camera_add()
        cam = bpy.context.view_layer.objects.active
        bpy.context.scene.camera = cam
    all_corners = []
    for o in objs:
        for c in o.bound_box:
            all_corners.append(o.matrix_world @ Vector(c))
    cx = sum(c.x for c in all_corners) / len(all_corners)
    cy = sum(c.y for c in all_corners) / len(all_corners)
    cz = sum(c.z for c in all_corners) / len(all_corners)
    center = Vector((cx, cy, cz))
    max_size = max(
        max(p[i] for p in all_corners) - min(p[i] for p in all_corners)
        for i in range(3)
    )
    dist = max_size * extra
    if view == "front":
        cam.location = (center.x, center.y - dist, center.z + dist * 0.05)
    elif view == "back":
        cam.location = (center.x, center.y + dist, center.z + dist * 0.05)
    elif view == "side":
        cam.location = (center.x + dist, center.y, center.z + dist * 0.05)
    else:
        cam.location = (center.x + dist * 0.7, center.y - dist * 0.7, center.z + dist * 0.5)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    bpy.context.view_layer.update()


def setup_anime_material(obj, base_color, name):
    """Anime-style smooth material with proper vertex color cleanup."""
    obj.data.materials.clear()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.append(mat)
    attrs = list(obj.data.color_attributes.keys())
    for an in attrs:
        obj.data.color_attributes.remove(obj.data.color_attributes[an])
    obj.data.color_attributes.render_color_index = -1


def animeify(obj, sub_view=1, sub_render=1, solidify_thickness=0.0015,
             smooth_iterations=0, apply_modifiers=True):
    """Apply anime-style transformations:
    1. Shade smooth
    2. Laplacian smooth (geometry) to remove bumps
    3. Subdivision surface (Catmull-Clark) for soft anime curves
    4. Solidify for 3D print wall thickness
    5. Apply modifiers to bake the result
    """
    if obj is None or obj.type != "MESH":
        return
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    # 1. Smooth shading
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    # 2. Laplacian smooth (using bmesh)
    if smooth_iterations > 0:
        import bmesh
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            for _ in range(smooth_iterations):
                bmesh.ops.smooth_vert(
                    bm, verts=list(bm.verts),
                    factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True,
                )
            bm.to_mesh(obj.data)
        finally:
            bm.free()
        obj.data.update()
    # 3. Add subdivision surface modifier
    mod_sub = obj.modifiers.new("AnimeSubdivision", "SUBSURF")
    mod_sub.subdivision_type = "CATMULL_CLARK"
    mod_sub.levels = sub_view
    mod_sub.render_levels = sub_render
    # 4. Add solidify modifier (for 3D print wall thickness)
    if solidify_thickness > 0:
        mod_sol = obj.modifiers.new("PrintSolidify", "SOLIDIFY")
        mod_sol.thickness = solidify_thickness
        mod_sol.offset = 0.0
        mod_sol.use_even_offset = True
    # 5. Apply modifiers
    if apply_modifiers:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if solidify_thickness > 0:
            try:
                bpy.ops.object.modifier_apply(modifier="PrintSolidify")
            except Exception as e:
                print(f"  WARN: solidify apply failed: {e}")
        try:
            bpy.ops.object.modifier_apply(modifier="AnimeSubdivision")
        except Exception as e:
            print(f"  WARN: subdiv apply failed: {e}")
        obj.select_set(False)


# ==================================================================
# STEP 1: Render HAIR (part_2.001) BEFORE — already done in step1
# ==================================================================
print("=== STEP 1: HAIR BEFORE (raw) ===")
hair = bpy.data.objects.get("part_2.001")
print(f"  hair: {hair.name if hair else 'MISSING'}")
print(f"  verts: {len(hair.data.vertices)}")
print(f"  bbox: {hair.dimensions}")

# ==================================================================
# STEP 2: Animate-ify the HAIR
# ==================================================================
print("\n=== STEP 2: ANIME-IFY the HAIR ===")
# Lower subdivision for safety; 1.5mm wall = printable
animeify(hair, sub_view=1, sub_render=1, solidify_thickness=0.0015,
         smooth_iterations=0, apply_modifiers=True)
setup_anime_material(hair, (0.92, 0.92, 0.95, 1.0), "AFR_HairMat_Anime")
print(f"  hair verts after: {len(hair.data.vertices)}")

# Save the hair-ified version
bpy.ops.wm.save_as_mainfile(
    filepath=os.path.join(OUT_DIR, "step2_hair_animed.blend"))

# Render hair AFTER
print("\n=== Render HAIR AFTER ===")
for o in bpy.data.objects:
    o.hide_render = (o is not hair)
    o.hide_viewport = (o is not hair)
frame_on([hair], view="diag", extra=1.8)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "02_HAIR_AFTER_diag.png")
bpy.ops.render.render(write_still=True)
print("  saved 02_HAIR_AFTER_diag.png")
frame_on([hair], view="side", extra=1.8)
bpy.context.scene.render.filepath = os.path.join(OUT_DIR, "02_HAIR_AFTER_side.png")
bpy.ops.render.render(write_still=True)
print("  saved 02_HAIR_AFTER_side.png")

# ==================================================================
# STEP 3: Render OTHER parts (part_0..12 + part_0.001..8.001)
# ==================================================================
print("\n=== STEP 3: list all mesh parts ===")
all_mesh = sorted(
    [o for o in bpy.data.objects
     if o.type == "MESH" and not o.name.startswith("Mesh_")
     and o.name not in {"Camera", "Light"}],
    key=lambda o: o.name,
)
for p in all_mesh:
    print(f"  {p.name}: v={len(p.data.vertices)}, dim={list(p.dimensions)}")

# Save
print("\nDone. Saved step2_hair_animed.blend")
