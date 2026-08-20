"""Domain tools exposed to the AI agent over MCP.

Every function is *pure* on the server side: it only constructs a snippet
of Blender-side Python (which assigns to ``AFR_RESULT``) and ships it to a
:class:`backend.BlenderBackend`. None of these import ``bpy`` — all Blender
work happens in the wrapped code that runs inside Blender.
"""

from __future__ import annotations

from .backend import BlenderBackend, _extract_result
from . import codegen


def _run(backend: BlenderBackend, body: str) -> dict:
    code = codegen.wrap(body)
    out = backend.execute_code(code)
    return _extract_result(out)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def list_objects(backend: BlenderBackend) -> dict:
    body = (
        "objs = [o for o in bpy.data.objects if o.type == 'MESH']\n"
        "AFR_RESULT = {\n"
        "    'count': len(objs),\n"
        "    'objects': [{'name': o.name, 'verts': len(o.data.vertices),\n"
        "                 'faces': len(o.data.polygons)} for o in objs],\n"
        "}\n"
    )
    return _run(backend, body)


def run_blender_code(backend: BlenderBackend, code: str) -> dict:
    """Execute arbitrary Blender Python. The ``code`` must set
    ``AFR_RESULT`` (a JSON-serialisable dict)."""
    return _run(backend, code)


# ---------------------------------------------------------------------------
# Mesh QA
# ---------------------------------------------------------------------------
def diagnose(backend: BlenderBackend, object_name: str | None = None) -> dict:
    body = (
        "from ai_figure_refiner.geometry import diagnostics as geo_diag\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    res = geo_diag.analyze_object(obj)\n"
        "    AFR_RESULT = res\n"
    ) % (object_name,)
    return _run(backend, body)


def repair(backend: BlenderBackend, object_name: str | None = None) -> dict:
    body = (
        "from ai_figure_refiner.geometry import repair as geo_repair\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    info = geo_repair.repair_basic(obj, remove_doubles_dist=0.001,\n"
        "                                   fill_holes=True, recalc_normals=True)\n"
        "    AFR_RESULT = {'repaired': True, 'log': info}\n"
    ) % (object_name,)
    return _run(backend, body)


def printability(backend: BlenderBackend, object_name: str | None = None,
                 min_wall_mm: float = 0.8, nozzle_mm: float = 0.4,
                 layer_height_mm: float = 0.2,
                 overhang_angle_deg: float = 45.0) -> dict:
    body = (
        "from ai_figure_refiner.geometry import printability as geo_print\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    res = geo_print.analyze_printability(\n"
        "        obj, min_wall_mm=%r, nozzle_mm=%r,\n"
        "        layer_height_mm=%r, overhang_angle_deg=%r)\n"
        "    AFR_RESULT = res\n"
    ) % (object_name, min_wall_mm, nozzle_mm, layer_height_mm,
         overhang_angle_deg)
    return _run(backend, body)


# ---------------------------------------------------------------------------
# Semantic labelling
# ---------------------------------------------------------------------------
def label_parts(backend: BlenderBackend, object_name: str | None = None,
                method: str = "heuristics") -> dict:
    body = (
        "from collections import Counter\n"
        "from ai_figure_refiner.semantic import parts as sem_parts\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    sem_parts.ensure_part_attribute(obj)\n"
        "    if %r == 'flood_body':\n"
        "        labels = sem_parts.brush_flood(obj, sem_parts.PART_ID['BODY'])\n"
        "    else:\n"
        "        labels = sem_parts.apply_heuristics(obj)\n"
        "    cnt = Counter(sem_parts.ID_PART[l] for l in labels)\n"
        "    AFR_RESULT = {'vertices': len(labels),\n"
        "                  'counts': dict(cnt.most_common())}\n"
    ) % (object_name, method)
    return _run(backend, body)


# ---------------------------------------------------------------------------
# Part-specific refinement
# ---------------------------------------------------------------------------
def process_hair(backend: BlenderBackend, object_name: str | None = None,
                 thickness_mm: float = 0.4) -> dict:
    body = (
        "from ai_figure_refiner.parts_ops import hair as hair_ops\n"
        "from ai_figure_refiner.semantic import parts as sem_parts\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    sem_parts.ensure_part_attribute(obj)\n"
        "    sem_parts.apply_heuristics(obj)\n"
        "    new = hair_ops.extract_part(obj, sem_parts.PART_ID['HAIR'])\n"
        "    if new is None:\n"
        "        AFR_RESULT = {'error': 'no HAIR vertices found'}\n"
        "    else:\n"
        "        ok = hair_ops.solidify_part(new, thickness=%r)\n"
        "        AFR_RESULT = {'hair_object': new.name, 'solidified': ok}\n"
    ) % (object_name, thickness_mm)
    return _run(backend, body)


def process_fabric(backend: BlenderBackend, object_name: str | None = None,
                   thickness_mm: float = 0.6) -> dict:
    body = (
        "from ai_figure_refiner.parts_ops import generic as generic_ops\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    generic_ops.solidify_fabric(obj, thickness=%r)\n"
        "    AFR_RESULT = {'object': obj.name, 'thickness_mm': %r}\n"
    ) % (object_name, thickness_mm, thickness_mm)
    return _run(backend, body)


def process_base(backend: BlenderBackend, object_name: str | None = None,
                 height_mm: float = 3.0, radius_mm: float = 0.0) -> dict:
    body = (
        "from ai_figure_refiner.parts_ops import generic as generic_ops\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    rad = %r if %r > 0 else None\n"
        "    base = generic_ops.generate_base(bpy.context.scene, obj,\n"
        "                                     radius=rad, height=%r)\n"
        "    AFR_RESULT = {'base_object': base.name}\n"
    ) % (object_name, radius_mm, radius_mm, height_mm)
    return _run(backend, body)


def merge_parts(backend: BlenderBackend, names: list[str]) -> dict:
    names_repr = repr(list(names))
    body = (
        "from ai_figure_refiner.parts_ops import generic as generic_ops\n"
        "sel = [bpy.data.objects.get(n) for n in %s\n"
        "       if bpy.data.objects.get(n) and bpy.data.objects.get(n).type == 'MESH']\n"
        "if len(sel) < 2:\n"
        "    AFR_RESULT = {'error': 'need >= 2 mesh objects, got %%d' %% len(sel)}\n"
        "else:\n"
        "    merged = generic_ops.merge_parts(bpy.context.scene, sel)\n"
        "    AFR_RESULT = {'merged_object': merged.name, 'sources': [o.name for o in sel]}\n"
    ) % (names_repr,)
    return _run(backend, body)


def auto_orient(backend: BlenderBackend, object_name: str | None = None) -> dict:
    body = (
        "from ai_figure_refiner.parts_ops import generic as generic_ops\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    r = generic_ops.auto_orient(obj)\n"
        "    AFR_RESULT = {'offset': [round(x, 3) for x in r[3:6]]}\n"
    ) % (object_name,)
    return _run(backend, body)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_3mf(backend: BlenderBackend, filepath: str,
               object_name: str | None = None) -> dict:
    body = (
        "from ai_figure_refiner.exporter import three_mf as exp_3mf\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    res = exp_3mf.export_3mf(obj, %r)\n"
        "    AFR_RESULT = {'filepath': res['filepath'],\n"
        "                  'vertices': res.get('vertices'),\n"
        "                  'triangles': res.get('triangles')}\n"
    ) % (object_name, filepath)
    return _run(backend, body)


# ---------------------------------------------------------------------------
# Connectors (convex/concave assembly joints)
# ---------------------------------------------------------------------------
def create_connector(backend: BlenderBackend, kind: str = "round",
                     position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0),
                     diameter: float = 5.0, depth: float = 4.0,
                     length: float = 4.0, clearance: float = 0.2,
                     nozzle_mm: float = 0.4, with_flange: bool = False,
                     chamfer: bool = True, opening_ratio: float = 0.7,
                     name: str = "AFR_Connector") -> dict:
    body = (
        "from ai_figure_refiner.parts_ops import connectors as connector_ops\n"
        "res = connector_ops.create_connector(\n"
        "    bpy.context.scene, kind=%r, position=%r, direction=%r,\n"
        "    diameter=%r, depth=%r, length=%r, clearance=%r,\n"
        "    nozzle_mm=%r, with_flange=%r, chamfer=%r,\n"
        "    opening_ratio=%r, name=%r)\n"
        "AFR_RESULT = {\n"
        "    'kind': res['kind'],\n"
        "    'male': res['male'].name if res.get('male') else None,\n"
        "    'female_cutter': res['female_cutter'].name\n"
        "                    if res.get('female_cutter') else None,\n"
        "    'params': res['params'],\n"
        "}\n"
    ) % (kind, tuple(position), tuple(direction), diameter, depth, length,
         clearance, nozzle_mm, with_flange, chamfer, opening_ratio, name)
    return _run(backend, body)


def carve_socket(backend: BlenderBackend, target_name: str,
                 cutter_name: str, apply: bool = True) -> dict:
    body = (
        "from ai_figure_refiner.parts_ops import connectors as connector_ops\n"
        "tgt = bpy.data.objects.get(%r)\n"
        "cut = bpy.data.objects.get(%r)\n"
        "if tgt is None or cut is None:\n"
        "    AFR_RESULT = {'error': 'target or cutter not found'}\n"
        "else:\n"
        "    AFR_RESULT = connector_ops.carve_socket(\n"
        "        bpy.context.scene, tgt, cut, apply=%r)\n"
    ) % (target_name, cutter_name, apply)
    return _run(backend, body)
