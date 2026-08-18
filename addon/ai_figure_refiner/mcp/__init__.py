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
