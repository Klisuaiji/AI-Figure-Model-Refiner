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
import functools
import traceback


class AFRError(Exception):
    """Base error for the AI Figure Refiner plugin."""


class DiagnosticError(AFRError):
    pass


class RepairError(AFRError):
    pass


class ExportError(AFRError):
    pass


class DependencyError(AFRError):
    """Raised when an optional dependency (e.g. onnxruntime) is missing."""


def safe_run(logger=None):
    """Decorator: catches exceptions, logs them, returns None instead of
    raising. Keeps Blender's UI responsive even when a task fails."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as e:
                if logger is not None:
                    logger.error("%s failed: %s" % (getattr(fn, "__name__", "task"), e))
                traceback.print_exc()
                return None

        return wrapper

    return deco