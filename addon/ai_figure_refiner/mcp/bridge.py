"""In-addon Blender MCP bridge.

When the AFR addon is running inside Blender, this module opens a TCP
socket (default ``127.0.0.1:9876``) that speaks the same
``execute_blender_code`` JSON contract used by the community *Blender MCP*
addon. That lets an external AFR MCP server (or any Blender-MCP client)
drive this Blender instance.

Code is executed on Blender's **main thread** via ``bpy.app.timers`` (bpy
is not thread-safe), while the network I/O runs on a daemon thread.
"""

from __future__ import annotations

import io
import json
import socket
import sys
import threading
import traceback


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876


class BlenderMCPBridge:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = False
        self._lock = threading.Lock()
        self._pending: tuple | None = None  # (code, event, holder)

    # -- lifecycle --------------------------------------------------------
    def start(self) -> str:
        import bpy

        if self._sock is not None:
            return "already running"
        self._stop = False
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(4)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        if not bpy.app.timers.is_registered(self._pump):
            bpy.app.timers.register(self._pump, first_interval=0.05)
        return "listening on %s:%d" % (self.host, self.port)

    def stop(self) -> str:
        import bpy

        self._stop = True
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        try:
            bpy.app.timers.unregister(self._pump)
        except Exception:
            pass
        return "stopped"

    def is_running(self) -> bool:
        return self._sock is not None

    # -- main-thread executor (timer) ------------------------------------
    def _pump(self) -> float:
        with self._lock:
            pend = self._pending
            self._pending = None
        if pend is not None:
            code, event, holder = pend
            holder["value"] = self._exec(code)
            event.set()
        return 0.05  # keep the timer alive

    @staticmethod
    def _exec(code: str) -> str:
        stdout = io.StringIO()
        old = sys.stdout
        sys.stdout = stdout
        ns: dict = {}
        try:
            exec(compile(code, "<afr-bridge>", "exec"), ns)
            result = stdout.getvalue()
        except Exception:
            result = stdout.getvalue() + "\nERROR: " + traceback.format_exc(-3)
        finally:
            sys.stdout = old
        return result

    # -- network thread ---------------------------------------------------
    def _serve(self) -> None:
        while not self._stop and self._sock is not None:
            try:
                conn, _addr = self._sock.accept()
            except OSError:
                break
            try:
                self._handle(conn)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def _handle(self, conn: socket.socket) -> None:
        data = b""
        conn.settimeout(1.0)
        try:
            while b"\n" not in data:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        line = data.split(b"\n", 1)[0].decode("utf-8", "replace")
        try:
            msg = json.loads(line)
            code = msg.get("code") or (msg.get("data") or {}).get("code", "")
        except Exception:
            conn.sendall((json.dumps({"status": "error",
                                      "message": "invalid JSON"}) + "\n").encode())
            return
        event = threading.Event()
        holder: dict = {}
        with self._lock:
            self._pending = (code, event, holder)
        ok = event.wait(timeout=120)
        if not ok:
            resp = {"status": "error", "message": "execution timeout"}
        else:
            resp = {"status": "success", "result": holder.get("value", "")}
        try:
            conn.sendall((json.dumps(resp) + "\n").encode())
        except OSError:
            pass


# Module-level singleton so operators can start/stop one instance.
_BRIDGE = BlenderMCPBridge()


def start_bridge(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    global _BRIDGE
    if _BRIDGE.is_running():
        return "already running"
    _BRIDGE = BlenderMCPBridge(host, port)
    return _BRIDGE.start()


def stop_bridge() -> str:
    return _BRIDGE.stop()


def bridge_status() -> str:
    return "running" if _BRIDGE.is_running() else "stopped"
