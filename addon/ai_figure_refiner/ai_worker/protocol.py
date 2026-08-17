"""AI inference worker protocol (Phase 12).

The Blender-side Python lacks ONNX Runtime, OpenCV, Pillow, etc. — so
all model inference runs in an external Python process (a "worker")
that talks to the addon over a JSON-over-stdio or JSON-over-HTTP line.

This module defines the wire schema and a serialiser, *not* the
worker itself. The worker script lives under `workers/` (a sibling to
this package) and is launched by `launcher.py` when the user triggers
an AI operation.

Schema v1:
  Request:
    {
      "id":        "<uuid>",
      "model":     "<model-name>",
      "task":      "<task-name>",
      "inputs":    { ... model-specific input dict ... }
    }
  Response:
    {
      "id":        "<uuid>",
      "ok":        true | false,
      "outputs":   { ... model-specific output dict ... },
      "error":     "<message>"   # only when ok == false
    }

Supported models (deferred to specific workers):
  - figure_seg : SAM/Dino segmentation of reference images -> part labels
  - depth      : Depth Anything -> per-view depth map
  - normal     : Normal estimation -> per-view normal map
  - hair_dense : Hair-dense generation -> vertices/strands
  - refine     : Generic mesh-refinement inpainter

Inputs and outputs are JSON-serialisable (vertices/faces are arrays of
numbers; images are base64 PNG strings). The worker may also write
large binary payloads to a side file referenced by `inputs.blob_path`.
"""
import json
import os
import time
import uuid


SCHEMA_VERSION = 1
SUPPORTED_MODELS = ("figure_seg", "depth", "normal", "hair_dense", "refine")


def make_request(model, task, inputs=None):
    """Build a JSON-serialisable request dict."""
    if model not in SUPPORTED_MODELS:
        raise ValueError("model %r not supported; pick from %s"
                         % (model, SUPPORTED_MODELS))
    return {
        "schema": SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "model": model,
        "task": task,
        "inputs": inputs or {},
    }


def encode_request(req):
    return json.dumps(req, ensure_ascii=False, separators=(",", ":"))


def decode_response(line):
    if not line.strip():
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": "JSON parse error: %s" % e}


def is_ok(resp):
    return isinstance(resp, dict) and resp.get("ok") is True


# ---------------------------------------------------------------------------
# Sync helpers (one-shot subprocess call)
# ---------------------------------------------------------------------------
def call_sync(worker_exe, request, timeout=300, cwd=None, env=None,
              python_executable=None):
    """Launch ``worker_exe``, write the JSON request on stdin, read one
    JSON response on stdout, return the response. The worker is
    expected to exit after producing the response (one-shot mode).

    If ``worker_exe`` ends in ``.py`` we automatically wrap it with
    ``python_executable`` (default ``sys.executable``), so the caller
    can pass either a binary or a Python script path."""
    import subprocess
    import sys as _sys
    if worker_exe is None:
        return {"ok": False, "error": "worker_exe is None"}
    if worker_exe.lower().endswith(".py"):
        py = python_executable or _sys.executable
        argv = [py, worker_exe]
    else:
        argv = [worker_exe]
    try:
        proc = subprocess.run(
            argv,
            input=encode_request(request) + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": "worker not found: %s" % e,
                "command": argv}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "error": "worker timed out after %ds" % timeout,
                "command": argv}
    if proc.returncode != 0 and not proc.stdout.strip():
        return {"ok": False,
                "error": "worker exit %d: %s" % (
                    proc.returncode, proc.stderr.strip()),
                "command": argv}
    return decode_response(proc.stdout) or {
        "ok": False, "error": "no response from worker"}


# ---------------------------------------------------------------------------
# Mesh → inputs (convenience)
# ---------------------------------------------------------------------------
def mesh_to_inputs(obj, max_vertices=200000):
    """Serialise a Blender mesh into the `inputs` dict for any worker that
    needs the geometry (refine, hair_dense, ...)."""
    if obj is None or obj.type != "MESH":
        raise ValueError("MESH required")
    import bmesh as _bm
    bm = _bm.new()
    try:
        try:
            bm.from_mesh(obj.data)
            bm.transform(obj.matrix_world)
            if len(bm.verts) > max_vertices:
                # uniform decimation would belong here; we just warn
                # via truncation rather than silently dropping data
                print("[AFR] mesh %s has %d verts > max_vertices=%d"
                      % (obj.name, len(bm.verts), max_vertices))
            vert_index = {v: i for i, v in enumerate(bm.verts)}
            vertices = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
            faces = []
            for f in bm.faces:
                idxs = [vert_index[v] for v in f.verts]
                faces.append(idxs)
            return {
                "object_name": obj.name,
                "vertices": vertices,
                "faces": faces,
            }
        except Exception as e:
            # Return a graceful empty payload rather than so the worker
            # crashes mid-stream. The worker can then decide to fallback.
            return {
                "object_name": obj.name,
                "vertices": [],
                "faces": [],
                "error": "mesh serialise failed: %s" % e,
            }
    finally:
        bm.free()