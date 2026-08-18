"""Process all figure parts with anime-style smoothing + 3D print solidify.
Saves the figure_only.blend for later assembly."""
import bpy
import bmesh
from mathutils import Vector
import os

OUT_DIR = r"D:\Qq203\Downloads\AI Figure Model Refiner\output\anime_workflow"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=r"D:\未命名.blend")

# Identify all figure parts (everything that is part of the figure)
figure_parts = []
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    if o.name in {"Light", "Camera"}:
        continue
    if o.name.startswith("Mesh_"):  # decorations
        continue
    figure_parts.append(o)
print(f"Figure parts: {[p.name for p in figure_parts]}")


def animeify(obj, smooth_factor=0.15, smooth_iters=3, thickness=0.0015,
             base_color=(0.85, 0.80, 0.75, 1.0), mat_name="AFR_FigureMat"):
    """Apply anime-style smoothing + solidify to one part."""
    if obj is None or obj.type != "MESH":
        return False
    print(f"  Processing {obj.name} (verts={len(obj.data.vertices)})...")
    # 1. Shade smooth
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    # 2. Gentle Laplacian smoothing
    for it in range(smooth_iters):
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bmesh.ops.smooth_vert(
                bm, verts=list(bm.verts),
                factor=smooth_factor,
                use_axis_x=True, use_axis_y=True, use_axis_z=True,
            )
            bm.to_mesh(obj.data)
        finally:
            bm.free()
        obj.data.update()
    # 3. Solidify 1.5mm
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mod_sol = obj.modifiers.new("PrintSolidify", "SOLIDIFY")
    mod_sol.thickness = thickness
    mod_sol.offset = 0.0
    mod_sol.use_even_offset = True
    try:
        bpy.ops.object.modifier_apply(modifier="PrintSolidify")
    except Exception as e:
        print(f"    WARN: solidify apply failed for {obj.name}: {e}")
    obj.select_set(False)
    # 4. Anime-style material
    obj.data.materials.clear()
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    out_n = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = 0.5
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out_n.inputs["Surface"])
    obj.data.materials.append(mat)
    # Clean color attrs
    attrs = list(obj.data.color_attributes.keys())
    for an in attrs:
        obj.data.color_attributes.remove(obj.data.color_attributes[an])
    obj.data.color_attributes.render_color_index = -1
    return True


# Determine color scheme for each part by inspecting structure
# Use the addon's semantic labels to pick a sensible color
import sys
ADDON_PARENT = r"D:\Qq203\Downloads\AI Figure Model Refiner\addon"
if ADDON_PARENT not in sys.path:
    sys.path.append(ADDON_PARENT)
try:
    import ai_figure_refiner
    ai_figure_refiner.register()
    from ai_figure_refiner.semantic.parts import (
        apply_heuristics, get_label_array, PART_ID, ID_PART,
    )
    has_addon = True
except Exception as e:
    has_addon = False
    print(f"  addon not available: {e}")


# Part-specific color scheme
part_colors = {
    "part_0.001": (0.95, 0.83, 0.50, 1.0),  # gold accent
    "part_1.001": (0.85, 0.80, 0.55, 1.0),  # lyre
    "part_2.001": (0.93, 0.93, 0.96, 1.0),  # silver hair (anime)
    "part_3.001": (0.42, 0.27, 0.14, 1.0),  # wood base
    "part_4.001": (0.92, 0.78, 0.50, 1.0),  # gold detail
    "part_5.001": (0.95, 0.83, 0.45, 1.0),  # gold accent
    "part_6.001": (0.78, 0.45, 0.30, 1.0),  # bronze detail
    "part_7.001": (0.78, 0.16, 0.16, 1.0),  # red mantle
    "part_8.001": (0.95, 0.92, 0.85, 1.0),  # white dress
}
# New split parts (user-added)
for p in [f"part_{i}" for i in range(13) if i != 7]:
    if p == "part_5":
        part_colors[p] = (0.97, 0.85, 0.78, 1.0)  # skin
    elif p == "part_6":
        part_colors[p] = (0.95, 0.92, 0.85, 1.0)  # white dress
    elif p == "part_0":
        part_colors[p] = (0.85, 0.65, 0.30, 1.0)  # gold bow
    elif p in {"part_2", "part_10"}:
        part_colors[p] = (0.97, 0.85, 0.78, 1.0)  # skin (foot)
    elif p in {"part_4", "part_8", "part_9", "part_1"}:
        part_colors[p] = (0.97, 0.85, 0.78, 1.0)  # skin (arm)
    elif p == "part_12":
        part_colors[p] = (0.97, 0.85, 0.78, 1.0)  # skin (hand)
    elif p == "part_11":
        part_colors[p] = (0.85, 0.65, 0.30, 1.0)  # gold detail
    elif p == "part_3":
        part_colors[p] = (0.78, 0.16, 0.16, 1.0)  # red
    else:
        part_colors[p] = (0.85, 0.80, 0.75, 1.0)

# Process all parts
for p in figure_parts:
    color = part_colors.get(p.name, (0.85, 0.80, 0.75, 1.0))
    animeify(p, base_color=color)

# Save
out = os.path.join(OUT_DIR, "figure_anime.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f"\nSaved {out}")
print(f"Total parts processed: {len(figure_parts)}")
