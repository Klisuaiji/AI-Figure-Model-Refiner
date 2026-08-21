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
"""Semantic part labeling module."""
from .parts import (PART_LABELS, PART_ID, ID_PART, PART_COLORS,
                    ensure_part_attribute, get_label_array, set_label_array,
                    set_vertex_color_overlay,
                    heuristics_label, apply_heuristics,
                    brush_apply, brush_smooth, brush_flood,
                    brush_grow, brush_shrink, brush_undo,
                    vote_labels, LabelHistory)