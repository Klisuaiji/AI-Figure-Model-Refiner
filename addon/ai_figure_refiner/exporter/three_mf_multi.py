"""Multi-object 3MF exporter (V0.6).

Extension to `three_mf.py` that adds support for:
  - multiple mesh objects in one .3mf file (each becomes its own
    <object id="N"> resource, all referenced from <build>).
  - nested components: a "model" object can have a <components> child
    referencing other objects, so the print plate can group parts
    hierarchically.
  - per-object build item transforms (translation in plate space).

ZIP layout still:
  [Content_Types].xml
  _rels/.rels
  3D/3dmodel.model

Each mesh is collected once; duplicate meshes are referenced by the
same object id (de-duplication).
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import bpy
import bmesh

from .three_mf import _gather_mesh, CONTENT_TYPES_XML, RELS_XML, NS_3MF

ET.register_namespace("", NS_3MF)


def _build_model_xml_multi(objects, components=None, unit="millimeter",
                           build_items=None):
    """Build a multi-object model XML.

    objects    : list of dicts:
                   {"id": int, "name": str, "vertices": [...], "triangles": [...]}
    components : optional list of dicts (one per "model" object):
                   {"id": int, "name": str, "components": [{"objectid": int, "transform": "..."}]}
    build_items: optional list of dicts:
                   {"objectid": int, "transform": "..."}   # transform = 12-number matrix (row-major)
    """
    root = ET.Element("{%s}model" % NS_3MF)
    root.set("unit", unit)

    resources = ET.SubElement(root, "{%s}resources" % NS_3MF)

    # plain mesh objects
    for obj in objects:
        o = ET.SubElement(resources, "{%s}object" % NS_3MF)
        o.set("id", str(obj["id"]))
        o.set("type", "model")
        o.set("name", obj.get("name", ""))
        mesh = ET.SubElement(o, "{%s}mesh" % NS_3MF)
        verts_el = ET.SubElement(mesh, "{%s}vertices" % NS_3MF)
        for vx, vy, vz in obj["vertices"]:
            v = ET.SubElement(verts_el, "{%s}vertex" % NS_3MF)
            v.set("x", "%g" % vx); v.set("y", "%g" % vy); v.set("z", "%g" % vz)
        tris_el = ET.SubElement(mesh, "{%s}triangles" % NS_3MF)
        for v1, v2, v3 in obj["triangles"]:
            t = ET.SubElement(tris_el, "{%s}triangle" % NS_3MF)
            t.set("v1", str(v1)); t.set("v2", str(v2)); t.set("v3", str(v3))

    # component-grouping objects
    if components:
        for comp in components:
            o = ET.SubElement(resources, "{%s}object" % NS_3MF)
            o.set("id", str(comp["id"]))
            o.set("type", "model")
            o.set("name", comp.get("name", ""))
            comps_el = ET.SubElement(o, "{%s}components" % NS_3MF)
            for sub in comp["components"]:
                c = ET.SubElement(comps_el, "{%s}component" % NS_3MF)
                c.set("objectid", str(sub["objectid"]))
                c.set("transform", sub.get("transform", identity_transform()))

    build = ET.SubElement(root, "{%s}build" % NS_3MF)
    if build_items is None:
        # default: instantiate every plain mesh object
        build_items = [{"objectid": obj["id"]} for obj in objects]
    for bi in build_items:
        item = ET.SubElement(build, "{%s}item" % NS_3MF)
        item.set("objectid", str(bi["objectid"]))
        if "transform" in bi:
            item.set("transform", bi["transform"])

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def identity_transform():
    """12-number row-major matrix: identity 3x4 (3MF convention)."""
    return "1 0 0 0 0 1 0 0 0 0 1 0"


def translate_transform(tx, ty, tz):
    """12-number row-major matrix with translation column."""
    return "1 0 0 %g 0 1 0 %g 0 0 1 %g" % (tx, ty, tz)


def _gather_all(scene_or_objects, name_prefix="obj"):
    """Collect meshes from a list of objects OR from the active scene's
    MESH objects. Returns (objects_list, mesh_cache).

    De-duplicates identical meshes by Blender data-block identity (so
    multiple users of the same mesh share one 3MF object id).
    """
    if isinstance(scene_or_objects, bpy.types.Scene):
        bobs = [o for o in scene_or_objects.objects if o.type == "MESH"]
    else:
        bobs = [o for o in scene_or_objects if o and o.type == "MESH"]
    cache = {}      # obj.data.name -> 3MF object id
    out_objects = []  # {id, name, vertices, triangles}
    next_id = 1
    for bobj in bobs:
        key = bobj.data.name
        if key in cache:
            continue
        name, verts, tris = _gather_mesh(bobj)
        oid = next_id
        next_id += 1
        cache[key] = oid
        out_objects.append({
            "id": oid, "name": name,
            "vertices": verts, "triangles": tris,
        })
    return out_objects, cache


def export_multi_3mf(filepath, scene_or_objects, build_items=None,
                     unit="millimeter"):
    """Write multiple mesh objects into one 3MF file.

    `build_items` is optional; if omitted, every collected mesh is
    instantiated at its world-space position (translation derived from
    the Blender object's matrix_world).
    """
    objs, cache = _gather_all(scene_or_objects)
    if not objs:
        raise ValueError("no MESH objects to export")

    if build_items is None:
        # derive a build_item per mesh, with world-space translation
        if isinstance(scene_or_objects, bpy.types.Scene):
            bobs = [o for o in scene_or_objects.objects if o.type == "MESH"]
        else:
            bobs = [o for o in scene_or_objects if o and o.type == "MESH"]
        build_items = []
        for bobj in bobs:
            oid = cache.get(bobj.data.name)
            if oid is None:
                continue
            loc = bobj.matrix_world.translation
            build_items.append({
                "objectid": oid,
                "transform": translate_transform(loc.x, loc.y, loc.z),
            })

    xml = _build_model_xml_multi(objs, components=None,
                                 unit=unit, build_items=build_items)
    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)
    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", RELS_XML)
        zf.writestr("3D/3dmodel.model", xml)
    return {
        "filepath": filepath,
        "object_count": len(objs),
        "build_item_count": len(build_items),
        "total_vertices": sum(len(o["vertices"]) for o in objs),
        "total_triangles": sum(len(o["triangles"]) for o in objs),
        "size_bytes": os.path.getsize(filepath),
        "written_utc": datetime.now(timezone.utc).isoformat(),
    }


def export_assembly_3mf(filepath, scene_or_objects, groups=None,
                        unit="millimeter"):
    """Write multiple mesh objects + optional grouping into a 3MF.

    groups: optional list of dicts:
        {"name": "AFR_Assembly", "objectids": [1, 2, 3]}
    The first group, if any, becomes the top-level build item.
    """
    objs, cache = _gather_all(scene_or_objects)
    if not objs:
        raise ValueError("no MESH objects to export")
    components = []
    next_id = max(o["id"] for o in objs) + 1
    group_objects = []
    build_items = []

    if isinstance(scene_or_objects, bpy.types.Scene):
        bobs = [o for o in scene_or_objects.objects if o.type == "MESH"]
    else:
        bobs = [o for o in scene_or_objects if o and o.type == "MESH"]

    for g in (groups or []):
        gid = next_id; next_id += 1
        comps = []
        for bobj in bobs:
            oid = cache.get(bobj.data.name)
            if oid is None:
                continue
            loc = bobj.matrix_world.translation
            comps.append({
                "objectid": oid,
                "transform": translate_transform(loc.x, loc.y, loc.z),
            })
        components.append({
            "id": gid, "name": g.get("name", "Group"),
            "components": comps,
        })
        build_items.append({"objectid": gid})
        group_objects.append(gid)

    if not group_objects:
        # no groups → behave like export_multi_3mf
        for bobj in bobs:
            oid = cache.get(bobj.data.name)
            if oid is None:
                continue
            loc = bobj.matrix_world.translation
            build_items.append({
                "objectid": oid,
                "transform": translate_transform(loc.x, loc.y, loc.z),
            })

    xml = _build_model_xml_multi(objs, components=components or None,
                                 unit=unit, build_items=build_items)
    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)
    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", RELS_XML)
        zf.writestr("3D/3dmodel.model", xml)
    return {
        "filepath": filepath,
        "mesh_object_count": len(objs),
        "group_count": len(components),
        "build_item_count": len(build_items),
        "total_vertices": sum(len(o["vertices"]) for o in objs),
        "total_triangles": sum(len(o["triangles"]) for o in objs),
        "size_bytes": os.path.getsize(filepath),
        "written_utc": datetime.now(timezone.utc).isoformat(),
    }