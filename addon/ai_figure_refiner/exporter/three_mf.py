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
"""3MF exporter (self-implemented).

Blender 5.2 LTS has no native 3MF import/export, so we write the spec
directly. The 3MF file is a ZIP archive containing at minimum:
  - [Content_Types].xml
  - _rels/.rels
  - 3D/3dmodel.model

The model XML describes one or more mesh objects. Each mesh object has
a single ``mesh`` resource with ``vertices`` and ``triangles``. This
exporter supports a single object per file (multi-object export would
require nested ``<object>`` and ``<components>`` resources, deferred
to V0.7).

Pure stdlib (zipfile + xml.etree). No Blender-side deps beyond
reading mesh data via bmesh.
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import bpy
import bmesh

# 3MF namespace
NS_3MF = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", NS_3MF)


CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
</Relationships>
"""


def _build_model_xml(obj_name, vertices, triangles, unit="millimeter"):
    """Construct the 3D model XML document.

    vertices: list of (x, y, z) tuples (in millimetres).
    triangles: list of (v1, v2, v3) int triples.
    """
    root = ET.Element("{%s}model" % NS_3MF)
    root.set("unit", unit)
    root.set("xmlns", NS_3MF)
    resources = ET.SubElement(root, "{%s}resources" % NS_3MF)
    obj = ET.SubElement(resources, "{%s}object" % NS_3MF)
    obj.set("id", "1")
    obj.set("type", "model")
    mesh = ET.SubElement(obj, "{%s}mesh" % NS_3MF)
    verts_el = ET.SubElement(mesh, "{%s}vertices" % NS_3MF)
    for vx, vy, vz in vertices:
        v = ET.SubElement(verts_el, "{%s}vertex" % NS_3MF)
        v.set("x", "%g" % vx)
        v.set("y", "%g" % vy)
        v.set("z", "%g" % vz)
    tris_el = ET.SubElement(mesh, "{%s}triangles" % NS_3MF)
    for v1, v2, v3 in triangles:
        t = ET.SubElement(tris_el, "{%s}triangle" % NS_3MF)
        t.set("v1", str(v1))
        t.set("v2", str(v2))
        t.set("v3", str(v3))
    build = ET.SubElement(root, "{%s}build" % NS_3MF)
    item = ET.SubElement(build, "{%s}item" % NS_3MF)
    item.set("objectid", "1")
    ET.SubElement(item, "{%s}metadatagroup" % NS_3MF)  # self-closing handled
    # pretty-print
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def _gather_mesh(obj):
    """Return (name, list-of-vertex-tuples, list-of-triangle-tuples)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        # triangulate for the 3MF spec (only triangles are required)
        bmesh.ops.triangulate(
            bm, faces=bm.faces[:], quad_method="BEAUTY",
            ngon_method="BEAUTY")
        verts = []
        for v in bm.verts:
            verts.append((v.co.x, v.co.y, v.co.z))
        # face vert index lookup using direct object refs (avoid
        # BMElemSeq indexed access, which is fragile in Blender 5.x)
        vert_index = {v: i for i, v in enumerate(bm.verts)}
        tris = []
        for f in bm.faces:
            v_idxs = [vert_index[v] for v in f.verts]
            if len(v_idxs) == 3:
                tris.append(tuple(v_idxs))
            else:
                # triangulate any leftover ngons by fan
                for i in range(1, len(v_idxs) - 1):
                    tris.append((v_idxs[0], v_idxs[i], v_idxs[i + 1]))
        return obj.name, verts, tris
    finally:
        bm.free()


def export_3mf(obj, filepath, unit="millimeter"):
    """Write ``obj`` as a 3MF file at ``filepath``."""
    name, verts, tris = _gather_mesh(obj)
    model_xml = _build_model_xml(name, verts, tris, unit=unit)
    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)
    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", RELS_XML)
        zf.writestr("3D/3dmodel.model", model_xml)
    return {
        "filepath": filepath,
        "object": name,
        "vertices": len(verts),
        "triangles": len(tris),
        "unit": unit,
        "size_bytes": os.path.getsize(filepath),
        "written_utc": datetime.now(timezone.utc).isoformat(),
    }