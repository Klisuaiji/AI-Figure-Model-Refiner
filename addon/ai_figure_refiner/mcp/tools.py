# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Klisuaiji (AI Figure Model Refiner)
# This file is part of the AI Figure Model Refiner (AFR) addon.
# AFR is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# AFR is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with AFR. If not, see <https://www.gnu.org/licenses/>.
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
def get_reference_images(backend: BlenderBackend) -> dict:
    """Return the 4 reference-image slots (FRONT/BACK/LEFT/RIGHT) with their
    file paths, loaded status and whether the mandatory FRONT photo is set.
    The multimodal AI agent reads these images to assist part labelling."""
    body = (
        "from ai_figure_refiner.reference import views as ref_views\n"
        "sc = bpy.context.scene\n"
        "ref_views.ensure_ref_state(sc)\n"
        "views = {}\n"
        "for v in sc.afr_ref_views:\n"
        "    views[v.name] = {'path': v.image_path or '',\n"
        "                     'loaded': bool(v.image_path),\n"
        "                     'camera': v.camera_obj or ''}\n"
        "front_ok = bool(views.get('FRONT', {}).get('loaded'))\n"
        "AFR_RESULT = {'views': views,\n"
        "             'front_required': True,\n"
        "             'front_present': front_ok,\n"
        "             'ready_for_multimodal': front_ok}\n"
    )
    return _run(backend, body)


def set_part_labels(backend: BlenderBackend, object_name: str | None,
                    labels: list) -> dict:
    """Write a per-vertex part-label array (list of ints, see PART_ID:
    0=UNLABELED 1=HAIR 2=HEAD 3=BODY 4=FABRIC 5=BASE) back to the object.
    Used by the multimodal agent to commit vision-derived labels."""
    body = (
        "from collections import Counter\n"
        "from ai_figure_refiner.semantic import parts as sem_parts\n"
        "obj = _get_object(%r)\n"
        "if obj is None:\n"
        "    AFR_RESULT = {'error': 'no source mesh object'}\n"
        "else:\n"
        "    labels = %r\n"
        "    sem_parts.ensure_part_attribute(obj)\n"
        "    sem_parts.set_label_array(obj, labels)\n"
        "    cnt = Counter(sem_parts.ID_PART[l] for l in labels)\n"
        "    AFR_RESULT = {'object': obj.name, 'vertices': len(labels),\n"
        "                  'counts': dict(cnt.most_common())}\n"
    ) % (object_name, labels)
    return _run(backend, body)


def label_parts(backend: BlenderBackend, object_name: str | None = None,
                method: str = "heuristics") -> dict:
    if method in ("vision", "multimodal"):
        # Front photo is MANDATORY for multimodal-assisted labeling.
        body = (
            "from ai_figure_refiner.reference import views as ref_views\n"
            "sc = bpy.context.scene\n"
            "ref_views.ensure_ref_state(sc)\n"
            "slot = ref_views.get_view_slot(sc, 'FRONT')\n"
            "if slot is None or not slot.image_path:\n"
            "    AFR_RESULT = {'error': '正面参考图未上传（多模态标注必需）：请先在 N 面板上传 FRONT 参考图'}\n"
            "else:\n"
            "    from collections import Counter\n"
            "    from ai_figure_refiner.semantic import parts as sem_parts\n"
            "    obj = _get_object(%r)\n"
            "    if obj is None:\n"
            "        AFR_RESULT = {'error': 'no source mesh object'}\n"
            "    else:\n"
            "        sem_parts.ensure_part_attribute(obj)\n"
            "        labels = sem_parts.apply_heuristics(obj)\n"
            "        cnt = Counter(sem_parts.ID_PART[l] for l in labels)\n"
            "        AFR_RESULT = {'vertices': len(labels),\n"
            "                      'counts': dict(cnt.most_common()),\n"
            "                      'front_image': slot.image_path,\n"
            "                      'method': 'heuristics+front_photo'}\n"
        ) % (object_name,)
        return _run(backend, body)
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
                     socket_wall_mm: float = 1.2,
                     name: str = "AFR_Connector") -> dict:
    body = (
        "from ai_figure_refiner.parts_ops import connectors as connector_ops\n"
        "res = connector_ops.create_connector(\n"
        "    bpy.context.scene, kind=%r, position=%r, direction=%r,\n"
        "    diameter=%r, depth=%r, length=%r, clearance=%r,\n"
        "    nozzle_mm=%r, with_flange=%r, chamfer=%r,\n"
        "    opening_ratio=%r, socket_wall_mm=%r, name=%r)\n"
        "AFR_RESULT = {\n"
        "    'kind': res['kind'],\n"
        "    'male': res['male'].name if res.get('male') else None,\n"
        "    'female_socket': res['female_socket'].name\n"
        "                       if res.get('female_socket') else None,\n"
        "    'female_cutter': res['female_cutter'].name\n"
        "                    if res.get('female_cutter') else None,\n"
        "    'params': res['params'],\n"
        "}\n"
    ) % (kind, tuple(position), tuple(direction), diameter, depth, length,
         clearance, nozzle_mm, with_flange, chamfer, opening_ratio,
         socket_wall_mm, name)
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
