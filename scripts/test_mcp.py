"""Test the AFR MCP server package without Blender.

Validates:
  * the MCP server module imports cleanly (no ``bpy`` required),
  * the expected tools are registered on the server,
  * every tool builds Blender-side code that (a) assigns ``AFR_RESULT``,
    (b) uses the ``codegen`` helpers (``_get_object``), and (c) references
    only modules that exist in the addon.

The Blender execution is simulated with a :class:`CaptureBackend` that records
the generated code instead of running it, so we exercise the whole
``tools -> codegen -> backend`` chain except the actual Blender run.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "addon"))

from ai_figure_refiner.mcp.backend import BlenderBackend, _extract_result  # noqa: E402
from ai_figure_refiner.mcp import tools as mcp_tools  # noqa: E402
from ai_figure_refiner.mcp import server as mcp_server  # noqa: E402


EXPECTED_TOOLS = [
    "list_objects", "diagnose", "repair", "printability", "label_parts",
    "process_hair", "process_fabric", "process_base", "merge_parts",
    "auto_orient", "export_3mf", "run_blender_code",
]

# Modules that the generated Blender-side code is allowed to import.
ALLOWED_AFR_IMPORTS = {
    "from ai_figure_refiner.geometry import diagnostics",
    "from ai_figure_refiner.geometry import repair",
    "from ai_figure_refiner.geometry import printability",
    "from ai_figure_refiner.semantic import parts",
    "from ai_figure_refiner.parts_ops import hair",
    "from ai_figure_refiner.parts_ops import generic",
    "from ai_figure_refiner.exporter import three_mf",
    "from collections import Counter",
}
# Plain stdlib names the codegen template / tool bodies may use.
ALLOWED_STDLIB = {"bpy", "sys", "io", "json", "traceback", "collections"}


class CaptureBackend(BlenderBackend):
    """Records the code that would run inside Blender and returns a stub."""

    def __init__(self):
        self.captured = []

    def execute_code(self, code: str) -> str:
        self.captured.append(code)
        return "__AFR_RESULT__" + '{"ok": true, "captured": true}'


def test_server_registration():
    mcp = mcp_server.mcp
    registered = [t.name for t in mcp._tool_manager.list_tools()]
    missing = [t for t in EXPECTED_TOOLS if t not in registered]
    assert not missing, f"missing tools: {missing}"
    print(f"[OK] server registered {len(registered)} tools: {registered}")
    return registered


def test_tools_build_valid_code():
    backend = CaptureBackend()
    calls = [
        ("list_objects", lambda: mcp_tools.list_objects(backend)),
        ("diagnose", lambda: mcp_tools.diagnose(backend, object_name="Foo")),
        ("repair", lambda: mcp_tools.repair(backend, object_name="Foo")),
        ("printability", lambda: mcp_tools.printability(backend, object_name="Foo")),
        ("label_parts", lambda: mcp_tools.label_parts(backend, object_name="Foo", method="heuristics")),
        ("process_hair", lambda: mcp_tools.process_hair(backend, object_name="Foo")),
        ("process_fabric", lambda: mcp_tools.process_fabric(backend, object_name="Foo")),
        ("process_base", lambda: mcp_tools.process_base(backend, object_name="Foo")),
        ("merge_parts", lambda: mcp_tools.merge_parts(backend, ["A", "B"])),
        ("auto_orient", lambda: mcp_tools.auto_orient(backend, object_name="Foo")),
        ("export_3mf", lambda: mcp_tools.export_3mf(backend, "/tmp/x.3mf", object_name="Foo")),
        ("run_blender_code", lambda: mcp_tools.run_blender_code(backend, "AFR_RESULT={'x':1}")),
    ]
    for name, fn in calls:
        backend.captured.clear()
        res = fn()
        assert backend.captured, f"{name}: no code generated"
        code = backend.captured[0]
        assert "_get_object" in code, f"{name}: missing _get_object helper"
        assert "AFR_RESULT" in code, f"{name}: does not assign AFR_RESULT"
        assert "_extract_result" and "__AFR_RESULT__" in code, f"{name}: missing sentinel"
        # every import line must be a known/allowed module
        for line in code.splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                if s in ALLOWED_AFR_IMPORTS:
                    continue
                # handle combined "import a, b, c" and "from x import y"
                if s.startswith("from "):
                    base = s.split(" as ")[0].strip()
                    assert base in ALLOWED_AFR_IMPORTS, f"{name}: unknown import -> {s}"
                else:
                    mods = [m.strip().split(" as ")[0].strip()
                            for m in s[len("import "):].split(",")]
                    assert all(m in ALLOWED_STDLIB for m in mods), \
                        f"{name}: unknown import -> {s}"
        assert res.get("ok") is True, f"{name}: bad result {res}"
    print(f"[OK] {len(calls)} tool code-gen checks passed")


def test_result_roundtrip():
    sample = 'some logs\n__AFR_RESULT__{"ok": true, "count": 3}'
    parsed = _extract_result(sample)
    assert parsed == {"ok": True, "count": 3}, parsed
    print("[OK] result sentinel roundtrip works")


def main():
    test_server_registration()
    test_tools_build_valid_code()
    test_result_roundtrip()
    print("\nALL MCP TESTS PASSED")


if __name__ == "__main__":
    main()
