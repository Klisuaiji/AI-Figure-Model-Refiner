"""Semantic part labeling module."""
from .parts import (PART_LABELS, PART_ID, ID_PART, PART_COLORS,
                    ensure_part_attribute, get_label_array, set_label_array,
                    set_vertex_color_overlay,
                    heuristics_label, apply_heuristics,
                    brush_apply, brush_smooth, brush_flood,
                    brush_grow, brush_shrink, brush_undo,
                    vote_labels, LabelHistory)