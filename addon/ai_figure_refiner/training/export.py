"""AI training data export (V0.7).

Produces a JSON manifest that downstream AI training can consume:

  {
    "schema": 1,
    "captured_utc": "...",
    "items": [
      {
        "id": "<uuid>",
        "object_name": "...",
        "vertices": [[x, y, z], ...],
        "faces": [[i, j, k], ...],
        "part_labels": [0, 1, 2, ...],     # per-vertex AFR_Part
        "ref_views": {
          "FRONT": {"image_path": "...", "camera": "..."},
          ...
        },
        "print_settings": {
          "nozzle_mm": 0.4,
          "layer_height_mm": 0.2,
          "min_wall_thickness_mm": 0.8,
          ...
        },
        "diagnostics": { ... },
        "printability": { ... }
      },
      ...
    ]
  }

The format is forward-compatible: consumers can ignore unknown fields.
"""
import json
import os
import time
import uuid


SCHEMA_VERSION = 1


def _serialize_object(obj, scene, ref_views_module=None, diagnostics=None,
                      printability=None):
    """Build a single training item dict from a Blender object + scene."""
    if obj is None or obj.type != "MESH":
        return None
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        vert_index = {v: i for i, v in enumerate(bm.verts)}
        vertices = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
        faces = [[vert_index[v] for v in f.verts] for f in bm.faces]
        # pull per-vertex labels
        part_labels = None
        if "AFR_Part" in obj.data.attributes:
            attr = obj.data.attributes["AFR_Part"]
            n = len(obj.data.vertices)
            if n > 0:
                part_labels = [0] * n
                attr.data.foreach_get("value", part_labels)
        item = {
            "id": str(uuid.uuid4()),
            "object_name": obj.name,
            "vertices": vertices,
            "faces": faces,
        }
        if part_labels is not None:
            item["part_labels"] = part_labels
        if diagnostics is not None:
            item["diagnostics"] = diagnostics
        if printability is not None:
            item["printability"] = printability
        if ref_views_module is not None and scene is not None:
            item["ref_views"] = _ref_views_snapshot(scene, ref_views_module)
        if scene is not None and hasattr(scene, "afr_print"):
            ps = scene.afr_print
            item["print_settings"] = {
                "nozzle_mm": ps.nozzle_mm,
                "layer_height_mm": ps.layer_height_mm,
                "material": ps.material,
                "min_wall_thickness_mm": ps.min_wall_thickness_mm,
                "density_g_cm3": ps.density_g_cm3,
            }
        return item
    finally:
        bm.free()


def _ref_views_snapshot(scene, ref_views_module):
    """Serialise reference view slots to a JSON-friendly dict."""
    out = {}
    if not hasattr(scene, "afr_ref_views"):
        return out
    for v in scene.afr_ref_views:
        out[v.name] = {
            "image_path": v.image_path,
            "camera": v.camera_obj,
        }
    return out


def export_training_data(scene, filepath, ref_views_module=None,
                         include_diagnostics=True, include_printability=True):
    """Export every MESH object in `scene` as a training item to a JSON
    file at `filepath`."""
    from ..geometry import diagnostics as geo_diag
    from ..geometry import printability as geo_print
    items = []
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        d = None
        p = None
        try:
            if include_diagnostics:
                d = geo_diag.analyze_object(obj)
        except Exception:
            pass
        try:
            if include_printability:
                ps = scene.afr_print
                p = geo_print.analyze_printability(
                    obj,
                    min_wall_mm=ps.min_wall_thickness_mm,
                    nozzle_mm=ps.nozzle_mm,
                    layer_height_mm=ps.layer_height_mm,
                    overhang_angle_deg=45.0)
        except Exception:
            pass
        item = _serialize_object(
            obj, scene, ref_views_module=ref_views_module,
            diagnostics=d, printability=p)
        if item is not None:
            items.append(item)
    manifest = {
        "schema": SCHEMA_VERSION,
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scene": scene.name,
        "item_count": len(items),
        "items": items,
    }
    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".",
                exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
    return {
        "filepath": filepath,
        "item_count": len(items),
        "size_bytes": os.path.getsize(filepath),
        "schema": SCHEMA_VERSION,
    }