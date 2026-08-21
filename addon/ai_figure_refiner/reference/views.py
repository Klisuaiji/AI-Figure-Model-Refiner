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
"""Reference image system.

Stores 4 reference views (Front/Back/Left/Right) plus their associated
cameras and background images. Used to align the imported model against
the artist's intent, drive 2D-to-3D projection and silhouette extraction.

Coordinate convention (Blender default):
  +Z up, -Y forward (camera looks down -Z by default in the user view,
  but the cameras here are positioned to look at the origin from each
  cardinal direction).
"""
import math

import bpy
from mathutils import Vector

VIEW_NAMES = ("FRONT", "BACK", "LEFT", "RIGHT")

# Each view: (camera position, look-at, up-axis name)
VIEW_PRESETS = {
    "FRONT": ((0.0, -3.0, 0.0), (0.0, 0.0, 0.0), "Z"),
    "BACK":  ((0.0,  3.0, 0.0), (0.0, 0.0, 0.0), "Z"),
    "LEFT":  ((-3.0, 0.0, 0.0), (0.0, 0.0, 0.0), "Z"),
    "RIGHT": (( 3.0, 0.0, 0.0), (0.0, 0.0, 0.0), "Z"),
}


# ---------------------------------------------------------------------------
# Data model (lightweight — 4 fixed slots, stored as Scene properties)
# ---------------------------------------------------------------------------
def ensure_ref_state(scene):
    """Make sure all 4 reference view slots exist on the scene."""
    if not hasattr(scene, "afr_ref_views") or scene.afr_ref_views is None:
        # scene property was not yet registered — defer.
        return None
    existing = {v.name for v in scene.afr_ref_views}
    for name in VIEW_NAMES:
        if name not in existing:
            v = scene.afr_ref_views.add()
            v.name = name
            v.image_path = ""
            v.camera_obj = ""
            v.scale = 1.0
            v.offset_x = 0.0
            v.offset_y = 0.0
            v.rotation_z = 0.0
    return scene.afr_ref_views


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------
def load_reference_image(scene, view_name, filepath):
    """Load (or reuse) an image from ``filepath`` into a Blender Image
    datablock and attach it as the background of the camera for
    ``view_name``. Returns the Image datablock."""
    if view_name not in VIEW_NAMES:
        raise ValueError("unknown view: %s" % view_name)
    if not filepath:
        raise ValueError("filepath required")
    name = "AFR_RefImg_" + view_name
    img = bpy.data.images.get(name)
    if img is None:
        try:
            img = bpy.data.images.load(filepath)
            img.name = name
        except Exception as e:
            raise RuntimeError("image load failed: %s" % e)
    else:
        # replace source
        try:
            img.filepath = filepath
            img.reload()
        except Exception:
            pass
    cam = get_or_create_camera(scene, view_name)
    attach_background(cam, img)
    # persist on ref slot
    slot = get_view_slot(scene, view_name)
    if slot is not None:
        slot.image_path = filepath
        slot.camera_obj = cam.name
    return img


def get_view_slot(scene, view_name):
    ensure_ref_state(scene)
    for v in scene.afr_ref_views:
        if v.name == view_name:
            return v
    return None


# ---------------------------------------------------------------------------
# Camera creation / alignment
# ---------------------------------------------------------------------------
def get_or_create_camera(scene, view_name):
    """Return the camera object for ``view_name``, creating it if absent."""
    if view_name not in VIEW_NAMES:
        raise ValueError("unknown view: %s" % view_name)
    cam_name = "AFR_RefCam_" + view_name
    cam = bpy.data.objects.get(cam_name)
    if cam is not None:
        return cam
    pos, target, up_str = VIEW_PRESETS[view_name]
    cam_data = bpy.data.cameras.new(name=cam_name + "_Data")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_obj = bpy.data.objects.new(cam_name, cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = Vector(pos)
    direction = Vector(target) - cam_obj.location
    rot = direction.to_track_quat("-Z", up_str).to_euler()
    cam_obj.rotation_euler = rot
    slot = get_view_slot(scene, view_name)
    if slot is not None:
        slot.camera_obj = cam_obj.name
    return cam_obj


def align_camera_to_bbox(scene, view_name, obj):
    """Re-aim the reference camera for ``view_name`` to frame ``obj``'s
    bounding box. Distance is set so the bbox fits the camera frustum at
    a comfortable margin."""
    if obj is None or obj.type != "MESH":
        raise ValueError("align_camera_to_bbox requires a MESH object")
    cam = get_or_create_camera(scene, view_name)
    pos, _t, up_str = VIEW_PRESETS[view_name]
    # bbox in world space
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    cx = sum(b.x for b in bbox) / 8.0
    cy = sum(b.y for b in bbox) / 8.0
    cz = sum(b.z for b in bbox) / 8.0
    center = Vector((cx, cy, cz))
    # largest dimension
    size = max(
        max(b.x for b in bbox) - min(b.x for b in bbox),
        max(b.y for b in bbox) - min(b.y for b in bbox),
        max(b.z for b in bbox) - min(b.z for b in bbox),
    )
    # fit size into a 50° lens with margin 1.6
    half = size * 0.5 * 1.6
    if half < 1e-6:
        half = 1.0
    # distance from camera (lens 50mm, sensor 36mm → half-fov ≈ atan(18/50))
    half_fov = math.atan(18.0 / 50.0)
    distance = half / math.tan(half_fov)
    direction = (center - Vector(pos)).normalized()
    if direction.length < 1e-6:
        direction = Vector(pos).normalized()
    # Camera stays on the preset side (opposite of inward direction).
    cam.location = center - direction * distance
    cam.rotation_euler = (
        (center - cam.location).to_track_quat("-Z", up_str).to_euler()
    )
    return cam


# ---------------------------------------------------------------------------
# Background image attachment
# ---------------------------------------------------------------------------
def attach_background(cam_obj, image):
    """Attach an Image as background of ``cam_obj`` (camera background)."""
    if cam_obj is None or cam_obj.type != "CAMERA":
        raise ValueError("expected a CAMERA object")
    bg = cam_obj.data.background_images
    bg.clear()
    item = bg.new()
    item.image = image
    item.frame_method = "FIT"
    item.alpha = 0.5
    item.display_depth = "BACK"
    return item


def detach_background(cam_obj):
    if cam_obj is None or cam_obj.type != "CAMERA":
        return
    cam_obj.data.background_images.clear()


# ---------------------------------------------------------------------------
# Silhouette extraction (analytical)
# ---------------------------------------------------------------------------
def silhouette_edges(bm, camera):
    """Return a list of BMesh edges that form the silhouette of ``bm`` as
    seen from ``camera``. An edge is a silhouette if exactly one of its
    two adjacent faces is front-facing the camera.
    """
    if camera is None or camera.type != "CAMERA":
        raise ValueError("camera required")
    cam_loc = camera.matrix_world.to_translation()
    edges_out = []
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        # Use face centroid direction from camera (avoid indexed access
        # since Blender 5.x BMesh seq tables are not auto-maintained).
        v1_first = f1.verts[0].co - cam_loc
        v2_first = f2.verts[0].co - cam_loc
        d1 = f1.normal.dot(v1_first)
        d2 = f2.normal.dot(v2_first)
        if (d1 > 0) != (d2 > 0):
            edges_out.append(e)
    return edges_out


def silhouette_edge_count(obj, camera):
    """Return count of silhouette edges as seen from ``camera``. Object
    is analyzed in world space."""
    import bmesh as _bm
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = _bm.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        return len(silhouette_edges(bm, camera))
    finally:
        bm.free()


def project_outline(obj, camera, samples_per_face=8):
    """Return a list of world-space points sampled on the silhouette as
    seen from ``camera``. Used for 2D-to-3D alignment heuristics. Each
    silhouette edge contributes its two endpoints; sample density is the
    same as the natural vertex resolution.
    """
    import bmesh as _bm
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    bm = _bm.new()
    try:
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        edges = silhouette_edges(bm, camera)
        pts = []
        seen = set()
        for e in edges:
            for v in e.verts:
                key = v.index
                if key not in seen:
                    seen.add(key)
                    pts.append((v.co.x, v.co.y, v.co.z))
        return pts
    finally:
        bm.free()