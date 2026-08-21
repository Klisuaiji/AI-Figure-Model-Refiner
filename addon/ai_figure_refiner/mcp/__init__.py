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
"""AI Figure Model Refiner — MCP interface.

Exposes an MCP server so an AI agent can drive Blender (diagnose, repair,
printability, label, refine hair/fabric/base, merge, export). Replaces the
old local ONNX worker: the "AI" is now an external agent reached through
MCP, and Blender is reached through the Blender MCP socket protocol.

Submodules:
  * ``backend``  — drives Blender (in-process or over the Blender MCP socket).
  * ``codegen``  — wraps tool code so it returns a parsed ``AFR_RESULT``.
  * ``tools``    — pure domain functions that build+run Blender-side code.
  * ``bridge``   — optional in-addon socket server (Blender MCP compatible).
  * ``server``   — the MCP server (requires the ``mcp`` SDK; run out-of-process).
"""

from __future__ import annotations

__version__ = "0.9.0"

from . import backend
from . import codegen
from . import tools
from . import bridge

__all__ = ["backend", "codegen", "tools", "bridge", "__version__"]
