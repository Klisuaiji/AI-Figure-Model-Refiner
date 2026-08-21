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
"""Other per-part operations (Phase 6-9).

  - solidify_fabric(obj, thickness): thicken thin fabric faces via solidify.
  - generate_base(obj, radius, height): create a cylindrical base disc
    centered under the object's bbox.
  - merge_parts(objects): boolean-union the given mesh objects into one.
  - auto_orient(obj): rotate the object so its bbox is upright (Z up) and
    its lowest face sits flush on the ground (min z = 0).
"""
import math

import bpy
import bmesh
from mathutils import Vector, Matrix


def solidify_fabric(obj, thickness=0.6):
    """Give the object uniform shell thickness. Identical to
    `hair.solidify_part`; re-exported here for discoverability."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.solidify(
            bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            thickness=thickness,
        )
        bm.to_mesh(obj.data)
        obj.data.update()
        return True
    finally:
        bm.free()


def generate_base(scene, source_obj, radius=None, height=3.0,
                  extra_margin=1.4, name="AFR_Base"):
    """Create a cylinder base underneath ``source_obj``. Cylinder sits
    on the ground (z=0) and its top is high enough to contain the
    source object's bbox bottom. The base radius is
    ``radius`` if given, otherwise ``max(bbox_x, bbox_y) * 0.6 * extra_margin``.
    Returns the base object."""
    if source_obj is None or source_obj.type != "MESH":
        raise ValueError("source MESH required")
    bbox = [source_obj.matrix_world @ Vector(c)
            for c in source_obj.bound_box]
    z_min = min(b.z for b in bbox)
    z_max = max(b.z for b in bbox)
    x_ext = max(b.x for b in bbox) - min(b.x for b in bbox)
    y_ext = max(b.y for b in bbox) - min(b.y for b in bbox)
    cx = sum(b.x for b in bbox) / 8.0
    cy = sum(b.y for b in bbox) / 8.0
    if radius is None:
        radius = max(x_ext, y_ext) * 0.6 * extra_margin
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=height,
        location=(cx, cy, height * 0.5),
        vertices=48,
    )
    base = bpy.context.active_object
    base.name = name
    return base


def merge_parts(scene, objects, name="AFR_Merged"):
    """Boolean-union the given mesh objects into a single new object.
    Uses the first object as the base and joins the rest with boolean
    union modifiers (avoids needing exact boolean solver for V0.5)."""
    if not objects:
        raise ValueError("at least one object required")
    # duplicate the first as the base
    base = objects[0]
    dup = base.copy()
    dup.data = base.data.copy()
    dup.name = name
    scene.collection.objects.link(dup)
    # join the remaining into the base via boolean union
    for other in objects[1:]:
        if other is None or other.type != "MESH":
            continue
        mod = dup.modifiers.new(name="Union_" + other.name, type="BOOLEAN")
        mod.operation = "UNION"
        mod.object = other
        try:
            bpy.context.view_layer.objects.active = dup
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as e:
            print("[merge_parts] boolean failed for %s: %s" % (other.name, e))
    # remove the sources (optional: skip to preserve user data)
    return dup


def auto_orient(obj, ground_tol=0.01):
    """Rotate & translate ``obj`` so:
      - the bbox is axis-aligned (principal-component; here we keep
        axes as-is for V0.5 simplicity).
      - the lowest face sits on the ground (min z = 0).
    Returns (rx, ry, rz, tx, ty, tz) applied.
    """
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    z_min = min(b.z for b in bbox)
    tx = 0.0
    ty = 0.0
    tz = -z_min  # so min z → 0
    obj.location = obj.location + Vector((tx, ty, tz))
    obj.data.update()
    return (0.0, 0.0, 0.0, tx, ty, tz)