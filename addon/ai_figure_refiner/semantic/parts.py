"""Semantic part labeling for AI figure models.

Five canonical parts: HAIR / HEAD / BODY / FABRIC / BASE. Labels are
stored per-vertex in an integer attribute on the mesh, making them
inspectable in Blender and round-trippable.

This module provides:
  - Source-of-truth enum + per-vertex attribute management.
  - Geometry-only heuristics for a first-pass labeling (no AI required).
  - A simple "voting" framework that future AI-segmentation outputs can
    plug into (multi-view voting).
  - Brush operations (Add/Remove/Smooth/Flood/Grow/Shrink/Undo).

Python dictionaries keyed by mesh name are the working state; results
are also written back to the mesh as a per-vertex ``AFR_Part`` integer
attribute, so other tools can read them without the addon.
"""
import bpy
import bmesh
from mathutils import Vector


# ---------------------------------------------------------------------------
# Canonical labels
# ---------------------------------------------------------------------------
PART_LABELS = ("UNLABELED", "HAIR", "HEAD", "BODY", "FABRIC", "BASE")
PART_ID = {n: i for i, n in enumerate(PART_LABELS)}
ID_PART = {i: n for i, n in enumerate(PART_LABELS)}

PART_COLORS = {
    "UNLABELED": (0.5, 0.5, 0.5, 1.0),
    "HAIR":      (0.85, 0.10, 0.85, 0.6),  # magenta
    "HEAD":      (0.95, 0.75, 0.55, 0.6),  # skin
    "BODY":      (0.30, 0.65, 0.95, 0.6),  # blue
    "FABRIC":    (0.95, 0.85, 0.20, 0.6),  # yellow
    "BASE":      (0.20, 0.85, 0.30, 0.6),  # green
}

ATTR_NAME = "AFR_Part"


# ---------------------------------------------------------------------------
# Per-vertex attribute storage (the source of truth)
# ---------------------------------------------------------------------------
def ensure_part_attribute(obj):
    """Make sure ``obj`` has an integer ``AFR_Part`` attribute on its
    mesh data. Existing attribute is reused; all values default to
    ``PART_ID['UNLABELED']`` (0).
    """
    if obj is None or obj.type != "MESH":
        raise ValueError("ensure_part_attribute requires a MESH object")
    me = obj.data
    if ATTR_NAME in me.attributes:
        return me.attributes[ATTR_NAME]
    attr = me.attributes.new(
        name=ATTR_NAME, type="INT", domain="POINT")
    # Initialise to UNLABELED (0)
    n = len(me.vertices)
    if n > 0:
        attr.data.foreach_set("value", [0] * n)
    return attr


def get_label_array(obj):
    """Return a Python list[int] of length len(obj.data.vertices)
    holding the current part label per vertex."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    attr = ensure_part_attribute(obj)
    n = len(obj.data.vertices)
    out = [0] * n
    if n > 0:
        attr.data.foreach_get("value", out)
    return out


def set_label_array(obj, labels):
    """Write a list[int] back to the per-vertex attribute."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    attr = ensure_part_attribute(obj)
    n = len(obj.data.vertices)
    if len(labels) != n:
        raise ValueError("length mismatch: %d vs %d" % (len(labels), n))
    for v in labels:
        if v not in ID_PART:
            raise ValueError("unknown label id %d" % v)
    attr.data.foreach_set("value", labels)
    obj.data.update()


def set_vertex_color_overlay(obj, labels=None):
    """Set per-vertex color to the part palette, so the user can see
    labels in the viewport. Creates a Color attribute if absent."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    if labels is None:
        labels = get_label_array(obj)
    me = obj.data
    color_attr = me.color_attributes.get("AFR_PartColor")
    if color_attr is None:
        color_attr = me.color_attributes.new(
            name="AFR_PartColor", type="BYTE_COLOR", domain="POINT")
    n = len(me.vertices)
    if n == 0:
        return
    rgba = []
    for lab in labels:
        c = PART_COLORS[ID_PART.get(lab, "UNLABELED")]
        rgba.extend(c)
    color_attr.data.foreach_set("color", rgba)
    obj.data.update()


# ---------------------------------------------------------------------------
# Geometry-only heuristics (no AI needed)
# ---------------------------------------------------------------------------
def heuristics_label(obj):
    """Apply a first-pass geometry heuristic to the mesh:
      - BASE: vertices in the lowest 12% of the bbox (z range).
      - HAIR: vertices in the top 40% (z) AND outside the central X/Y bbox
              (i.e. beyond the head's central cross-section).
      - HEAD: top 40% vertices INSIDE the central X/Y bbox.
      - BODY: middle band (between BASE and HAIR caps), default label.
      - FABRIC: vertices attached to BODY via down-hanging faces (faces
                whose normal tilts downward, used as a fabric hint).
    Returns the label list (length = vertex count).
    """
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    me = obj.data
    n = len(me.vertices)
    if n == 0:
        return []
    zs = [v.co.z for v in me.vertices]
    z_min, z_max = min(zs), max(zs)
    z_range = z_max - z_min
    if z_range < 1e-9:
        return [PART_ID["BODY"]] * n
    # central cross-section (1/3 around bbox centre) = head region
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    xc = (x_min + x_max) * 0.5
    yc = (y_min + y_max) * 0.5
    central_r = min(x_max - x_min, y_max - y_min) * 0.5
    labels = [PART_ID["UNLABELED"]] * n
    for i, v in enumerate(me.vertices):
        z = v.co.z
        # BASE: lowest 12%
        if z <= z_min + z_range * 0.12:
            labels[i] = PART_ID["BASE"]
        # HAIR/HEAD: top 40%
        elif z >= z_max - z_range * 0.40:
            dx = v.co.x - xc
            dy = v.co.y - yc
            if (dx * dx + dy * dy) <= central_r * central_r:
                labels[i] = PART_ID["HEAD"]
            else:
                labels[i] = PART_ID["HAIR"]
        else:
            labels[i] = PART_ID["BODY"]
    # FABRIC refinement: faces whose normal tilts downward and whose
    # all 3 verts are currently BODY -> mark as FABRIC.
    for f in me.polygons:
        if f.normal.z > -0.3:
            continue
        if all(labels[v] == PART_ID["BODY"] for v in f.vertices):
            for vi in f.vertices:
                labels[vi] = PART_ID["FABRIC"]
    return labels


def apply_heuristics(obj):
    labels = heuristics_label(obj)
    set_label_array(obj, labels)
    set_vertex_color_overlay(obj, labels)
    return labels


# ---------------------------------------------------------------------------
# Brush operations (Add/Remove/Smooth/Flood/Grow/Shrink/Undo)
# ---------------------------------------------------------------------------
class LabelHistory:
    """Per-object undo stack for label changes."""
    _stack = {}

    @classmethod
    def push(cls, obj, labels):
        key = obj.name
        if key not in cls._stack:
            cls._stack[key] = []
        cls._stack[key].append(labels)
        if len(cls._stack[key]) > 30:
            cls._stack[key].pop(0)

    @classmethod
    def pop(cls, obj):
        key = obj.name
        if key not in cls._stack or not cls._stack[key]:
            return None
        return cls._stack[key].pop()


def brush_apply(obj, mask_indices, label_id, mode="add"):
    """Apply a brush label to vertices at indices in ``mask_indices``.

    Modes:
      - add   : set label only where currently UNLABELED or same label
      - overwrite : force label
      - remove : set to UNLABELED where currently this label
    Returns the new labels list.
    """
    if label_id not in ID_PART:
        raise ValueError("unknown label id %d" % label_id)
    labels = get_label_array(obj)
    LabelHistory.push(obj, list(labels))
    for i in mask_indices:
        if i < 0 or i >= len(labels):
            continue
        if mode == "add":
            if labels[i] != label_id:
                labels[i] = label_id
        elif mode == "overwrite":
            labels[i] = label_id
        elif mode == "remove":
            if labels[i] == label_id:
                labels[i] = PART_ID["UNLABELED"]
    set_label_array(obj, labels)
    set_vertex_color_overlay(obj, labels)
    return labels


def brush_smooth(obj, mask_indices, label_id, neighbor_radius=1):
    """Dilate ``label_id`` into adjacent UNLABELED vertices within the
    mask (one-ring neighbour expansion)."""
    labels = get_label_array(obj)
    LabelHistory.push(obj, list(labels))
    # Build adjacency
    adj = {i: set() for i in mask_indices}
    for e in obj.data.edges:
        a, b = e.vertices[0], e.vertices[1]
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    # One-ring expansion within mask
    expanded = set(mask_indices)
    for _ in range(max(1, neighbor_radius)):
        new_set = set(expanded)
        for i in expanded:
            for nb in adj.get(i, ()):
                if nb in mask_indices and labels[nb] == PART_ID["UNLABELED"]:
                    new_set.add(nb)
        expanded = new_set
    for i in expanded:
        if labels[i] == PART_ID["UNLABELED"] or labels[i] == label_id:
            labels[i] = label_id
    set_label_array(obj, labels)
    set_vertex_color_overlay(obj, labels)
    return labels


def brush_flood(obj, label_id):
    """Set every vertex to ``label_id``."""
    n = len(obj.data.vertices)
    labels = [label_id] * n
    LabelHistory.push(obj, get_label_array(obj))
    set_label_array(obj, labels)
    set_vertex_color_overlay(obj, labels)
    return labels


def brush_grow(obj, mask_indices, label_id, iterations=1):
    """Grow the masked region outward by one ring per iteration."""
    labels = get_label_array(obj)
    LabelHistory.push(obj, list(labels))
    region = set(mask_indices)
    for _ in range(iterations):
        adj = set()
        for e in obj.data.edges:
            a, b = e.vertices[0], e.vertices[1]
            if a in region and b not in region:
                adj.add(b)
            elif b in region and a not in region:
                adj.add(a)
        region |= adj
    for i in region:
        labels[i] = label_id
    set_label_array(obj, labels)
    set_vertex_color_overlay(obj, labels)
    return labels


def brush_shrink(obj, mask_indices, label_id, iterations=1):
    """Shrink the masked region: vertices not connected to the seed
    interior get cleared to UNLABELED."""
    labels = get_label_array(obj)
    LabelHistory.push(obj, list(labels))
    seed = set(mask_indices)
    for _ in range(iterations):
        # boundary = vertices in seed with at least one edge to outside
        boundary = set()
        for e in obj.data.edges:
            a, b = e.vertices[0], e.vertices[1]
            if a in seed and b not in seed:
                boundary.add(a)
            elif b in seed and a not in seed:
                boundary.add(b)
        seed -= boundary
    for i in mask_indices:
        if i not in seed:
            labels[i] = PART_ID["UNLABELED"]
        else:
            labels[i] = label_id
    set_label_array(obj, labels)
    set_vertex_color_overlay(obj, labels)
    return labels


def brush_undo(obj):
    prev = LabelHistory.pop(obj)
    if prev is None:
        return None
    set_label_array(obj, prev)
    set_vertex_color_overlay(obj, prev)
    return prev


# ---------------------------------------------------------------------------
# Multi-view voting (placeholder for AI segmentation input)
# ---------------------------------------------------------------------------
def vote_labels(views_labels):
    """Given a list of label-arrays from N views (same vertex count),
    return the majority label per vertex. Ties go to the first vote."""
    if not views_labels:
        return []
    n = len(views_labels[0])
    out = [0] * n
    for i in range(n):
        counts = {}
        for arr in views_labels:
            if i >= len(arr):
                continue
            v = arr[i]
            counts[v] = counts.get(v, 0) + 1
        if counts:
            best = max(counts.items(), key=lambda kv: kv[1])[0]
            out[i] = best
    return out