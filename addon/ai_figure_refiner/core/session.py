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
import bpy


class Snapshot:
    """Captures a mesh datablock copy so it can be restored later."""

    def __init__(self, obj):
        self.obj = obj
        self.name = obj.name
        self.data_copy = obj.data.copy()

    def restore(self):
        obj = self.obj
        old = obj.data
        obj.data = self.data_copy
        try:
            bpy.data.meshes.remove(old)
        except Exception:
            pass
        return obj


class Part:
    """Lightweight semantic part record. Python data is the source of
    truth — Geometry Nodes / attributes are only for visualisation."""

    def __init__(self, pid, name, ptype, obj=None, confidence=0.0):
        self.id = pid
        self.name = name
        self.type = ptype  # hair / head / body / fabric / base / other
        self.object = obj
        self.confidence = confidence
        self.status = "pending"
        self.thickness_mm = 0.0
        self.print_priority = 0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "object": self.object.name if self.object else None,
            "confidence": self.confidence,
            "status": self.status,
            "thickness_mm": self.thickness_mm,
            "print_priority": self.print_priority,
        }


class RepairSession:
    """Top-level per-model session object."""

    def __init__(self):
        self.session_id = None
        self.source_object = None
        self.reference_images = {}
        self.parts = []
        self.current_step = 0
        self.diagnostics = None
        self.settings = {}
        self._snapshots = []
        self.history = []

    def push_snapshot(self, obj):
        if obj is None:
            return None
        snap = Snapshot(obj)
        self._snapshots.append(snap)
        self.history.append("snapshot:%s" % obj.name)
        return snap

    def rollback(self):
        if not self._snapshots:
            return False
        snap = self._snapshots.pop()
        snap.restore()
        self.history.append("rollback:%s" % snap.name)
        return True

    def snapshot_count(self):
        return len(self._snapshots)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "source_object": self.source_object.name if self.source_object else None,
            "current_step": self.current_step,
            "parts": [p.to_dict() for p in self.parts],
            "diagnostics": self.diagnostics,
            "snapshot_count": self.snapshot_count(),
            "history_len": len(self.history),
        }


session = RepairSession()