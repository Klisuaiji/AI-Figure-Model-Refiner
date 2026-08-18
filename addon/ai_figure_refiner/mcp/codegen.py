"""Code generation for the AFR MCP backend.

Tool callers (see :mod:`ai_figure_refiner.mcp.tools`) build short Python
*bodies* that run inside Blender and assign a dict to ``AFR_RESULT``. This
module wraps such a body into a full, self-contained script that:

* defines the small Blender-side helpers AFR tool bodies rely on
  (``_resolve_source`` / ``_get_object``),
* captures ``stdout`` so the AI agent sees logs,
* always terminates with a ``__AFR_RESULT__`` JSON sentinel that the
  backend parses back into a dict (see :func:`backend._extract_result`).
"""

from __future__ import annotations

RESULT_MARKER = "__AFR_RESULT__"

_TEMPLATE = '''\
import sys, io, json, traceback
import bpy

def _resolve_source():
    sc = bpy.context.scene
    obj = None
    if getattr(sc, "afr_source", ""):
        obj = sc.objects.get(sc.afr_source)
    if obj is None:
        obj = bpy.context.active_object
    return obj

def _get_object(name):
    if name:
        return bpy.data.objects.get(name)
    return _resolve_source()

_stdout = io.StringIO()
_old = sys.stdout
sys.stdout = _stdout
AFR_RESULT = {}
try:
__BODY__
except Exception:
    AFR_RESULT = {"error": traceback.format_exc(-3)}
finally:
    sys.stdout = _old
    _out = _stdout.getvalue()
    sys.stdout.write(_out)
    sys.stdout.write("\\n__AFR_RESULT__" + json.dumps(AFR_RESULT, ensure_ascii=False))
'''


def wrap(body: str) -> str:
    """Indent ``body`` and embed it in the AFR execution template."""
    indented = "\n".join(("    " + line) if line.strip() else line
                         for line in body.splitlines())
    return _TEMPLATE.replace("__BODY__", indented)


def build(imports: str, statements: str) -> str:
    """Convenience: compose a body from an import block + statements.

    ``statements`` must ultimately assign to ``AFR_RESULT``.
    """
    body = ""
    if imports.strip():
        body += imports.strip() + "\n"
    body += statements
    return wrap(body)
