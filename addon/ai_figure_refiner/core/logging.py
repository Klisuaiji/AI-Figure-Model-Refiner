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
import time
import traceback


class Logger:
    """Centralised logger. Writes to stdout and mirrors into the UI log
    collection ``bpy.types.Scene.afr_log`` when available."""

    MAX_LINES = 500

    def __init__(self, name="AFR"):
        self.name = name

    def _push_scene(self, level, text):
        try:
            sc = bpy.context.scene
            if not hasattr(sc, "afr_log"):
                return
            item = sc.afr_log.add()
            item.level = level
            item.text = text
            item.time = time.strftime("%H:%M:%S")
            # cap the log size
            while len(sc.afr_log) > self.MAX_LINES:
                sc.afr_log.remove(0)
        except (AttributeError, TypeError, KeyError):
            # scene / property not ready; safe to ignore during early
            # register() or during scene reload.
            pass
        except Exception as e:
            # unexpected — print once but never propagate (the logger
            # must never raise, that would crash the calling operator).
            traceback.print_exc()
            print("[AFR logger internal] %s" % e)

    def log(self, level, text):
        line = "[%s] %s" % (level, text)
        print("%s %s" % (self.name, line))
        self._push_scene(level, text)
        return line

    def debug(self, t):
        return self.log("DEBUG", t)

    def info(self, t):
        return self.log("INFO", t)

    def warning(self, t):
        return self.log("WARNING", t)

    def error(self, t):
        return self.log("ERROR", t)


logger = Logger()