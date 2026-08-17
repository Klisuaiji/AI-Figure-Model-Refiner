"""Worker launcher (Phase 12).

Discovers / starts the external Python worker that performs AI
inference. The worker itself is a separate Python program with
ONNX Runtime / OpenCV / Pillow available; it is *not* shipped with
this addon. By default we expect `afr_worker.py` on PATH or in
`workers/` next to the addon.
"""
import os
import sys


DEFAULT_WORKER_NAMES = (
    "afr_worker.py",
    "afr_worker.exe",
    "AFR_Worker.exe",
    "african-worker",  # unlikely, included for completeness
)


def find_worker(extra_paths=None):
    """Look for an AI worker binary on PATH or in known locations."""
    candidates = []
    here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    candidates.append(os.path.join(here, "workers"))
    if extra_paths:
        candidates.extend(extra_paths)
    for d in candidates:
        if not os.path.isdir(d):
            continue
        for name in DEFAULT_WORKER_NAMES:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
    # fallback: PATH lookup
    for name in DEFAULT_WORKER_NAMES:
        for p in os.environ.get("PATH", "").split(os.pathsep):
            full = os.path.join(p, name)
            if os.path.isfile(full):
                return full
    return None


def launch_or_message():
    """Either return the worker path or a diagnostic message (no
    subprocess is started here — the actual call lives in
    `protocol.call_sync`)."""
    p = find_worker()
    if p:
        return {"ok": True, "worker": p}
    return {
        "ok": False,
        "error": ("AI worker not found. Place `afr_worker.py` under "
                  "`<addon_dir>/workers/` or add its directory to PATH. "
                  "The worker should accept a JSON request on stdin and "
                  "emit one JSON response on stdout."),
        "searched": [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "workers"),
        ],
        "hint": ("Set up workers/ with a Python venv that has "
                 "`onnxruntime opencv-python numpy Pillow` installed."),
    }


def stub_worker_response(req):
    """Return a deterministic placeholder response when the worker is
    not available. Used so the UI can still operate and the user can
    see what a real worker would return."""
    return {
        "ok": True,
        "stub": True,
        "id": req.get("id"),
        "model": req.get("model"),
        "task": req.get("task"),
        "outputs": {
            "status": "worker_unavailable",
            "message": ("No AI worker detected. Returning placeholder. "
                        "Drop a Python worker into addon/ai_figure_refiner/workers/ "
                        "to enable real inference."),
            "echoed_inputs_keys": sorted((req.get("inputs") or {}).keys()),
        },
    }