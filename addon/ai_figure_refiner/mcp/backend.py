"""Blender backend for the AFR MCP server.

An AI agent reaches Blender through this backend. Two transports are
supported:

* ``InProcessBackend`` — the MCP server is launched from *inside* Blender's
  own Python (``bpy`` importable), so code runs directly in the host
  process. This is the fastest path and needs no socket.
* ``SocketBackend`` — the MCP server runs as a *separate* process and talks
  to a Blender instance over TCP using the same ``execute_blender_code``
  JSON contract as the community *Blender MCP* addon. This is what makes
  AFR "适配 Blender MCP": any Blender that exposes that socket (the upstream
  ``blender-mcp`` addon, or AFR's own in-addon bridge, see ``bridge.py``) is
  driveable.

The code that runs inside Blender is produced by :mod:`ai_figure_refiner.mcp.codegen`.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import traceback


# Default Blender MCP socket (matches the community blender-mcp addon).
DEFAULT_HOST = os.environ.get("AFR_BLENDER_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("AFR_BLENDER_PORT", "9876"))
SOCKET_TIMEOUT = float(os.environ.get("AFR_BLENDER_TIMEOUT", "120"))


def _bpy_available() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except Exception:
        return False


class BlenderBackend:
    """Abstract driver that executes Python code *inside* Blender and
    returns whatever the code printed to stdout (which, for AFR tool code,
    ends with a ``__AFR_RESULT__`` JSON sentinel — see ``codegen``)."""

    def execute_code(self, code: str) -> str:
        raise NotImplementedError

    # -- convenience used by tool callers ---------------------------------
    def health(self) -> dict:
        try:
            out = self.execute_code(
                "import bpy\n"
                "AFR_RESULT = {'blender': bpy.app.version_string, "
                "'objects': len(bpy.data.objects)}\n"
            )
            return _extract_result(out)
        except Exception as e:  # pragma: no cover - transport failure
            return {"ok": False, "error": str(e)}


class InProcessBackend(BlenderBackend):
    """Run code in the current process (must have ``bpy`` available)."""

    def __init__(self, namespace: dict | None = None):
        import bpy  # fail loudly at construction if not in Blender
        self._bpy = bpy
        self._ns = dict(namespace or {})

    def execute_code(self, code: str) -> str:
        import io

        stdout = io.StringIO()
        ns = dict(self._ns)
        ns.setdefault("bpy", self._bpy)
        old = sys.stdout
        sys.stdout = stdout
        try:
            exec(compile(code, "<afr-mcp>", "exec"), ns)
        except Exception:
            stdout.write("\n__AFR_RESULT__" + json.dumps(
                {"error": traceback.format_exc(-3)}))
        finally:
            sys.stdout = old
        return stdout.getvalue()


class SocketBackend(BlenderBackend):
    """Talk to a Blender MCP socket (localhost:9876 by default).

    Sends ``{"type": "execute_blender_code", "code": <code>}`` as a single
    newline-terminated JSON line and reads one JSON response back. The
    response's ``result`` field carries the code's stdout (which includes
    the ``__AFR_RESULT__`` sentinel).
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 timeout: float = SOCKET_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout

    def execute_code(self, code: str) -> str:
        payload = json.dumps(
            {"type": "execute_blender_code", "code": code})
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        try:
            sock.sendall((payload + "\n").encode("utf-8"))
            sock.settimeout(self.timeout)
            # Read until a full JSON line is received.
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
            line = buf.split(b"\n", 1)[0].decode("utf-8", "replace")
        finally:
            sock.close()
        try:
            resp = json.loads(line)
        except json.JSONDecodeError:
            return line  # raw stdout fallback
        if resp.get("status") == "error":
            raise RuntimeError(resp.get("message", "Blender MCP returned error"))
        # Some implementations nest the code stdout under "result".
        result = resp.get("result")
        if result is None and "message" in resp:
            result = resp.get("message")
        return result if isinstance(result, str) else json.dumps(result)


def get_default_backend() -> BlenderBackend:
    """Pick a backend: in-process when ``bpy`` is importable, otherwise a
    socket client to the Blender MCP endpoint."""
    if _bpy_available():
        return InProcessBackend()
    return SocketBackend()


def _extract_result(stdout_text: str) -> dict:
    """Pull the ``__AFR_RESULT__`` JSON sentinel out of code output."""
    marker = "__AFR_RESULT__"
    idx = stdout_text.rfind(marker)
    if idx == -1:
        return {"ok": True, "raw": stdout_text.strip()[-4000:]}
    body = stdout_text[idx + len(marker):].strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "error": "could not parse AFR_RESULT",
                "tail": body[-2000:]}
