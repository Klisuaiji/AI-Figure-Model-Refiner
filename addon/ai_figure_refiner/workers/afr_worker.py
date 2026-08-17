#!/usr/bin/env python3
"""AFR AI Worker — example skeleton (NOT a working inference binary).

This file is a **template** showing how to build a worker that the
Blender addon can call. The Blender addon expects:

  - Worker is invoked with no arguments (or with a JSON config file path).
  - Worker reads ONE JSON request from stdin (the format from
    `ai_figure_refiner.ai_worker.protocol`).
  - Worker writes ONE JSON response on stdout (same format).
  - Worker exits.

To make this a real worker:
  1. Install dependencies into a virtualenv:
       python -m venv addon/ai_figure_refiner/workers/venv
       addon/ai_figure_refiner/workers/venv/bin/pip install \\
           onnxruntime opencv-python numpy Pillow
  2. Replace `dispatch()` below with calls into your ONNX models.
  3. Add the worker directory to PATH, OR drop this file at
     addon/ai_figure_refiner/workers/afr_worker.py (auto-discovered).

Run the worker directly for a quick smoke test:

    echo '{"schema":1,"id":"abc","model":"figure_seg","task":"segment","inputs":{}}' \\
    | python afr_worker.py
"""
import json
import sys
import time


SUPPORTED = ("figure_seg", "depth", "normal", "hair_dense", "refine")


def dispatch(req):
    """Route a request to the right handler. Each handler should return
    a dict that becomes the `outputs` field of the response."""
    model = req.get("model")
    task = req.get("task")
    if model not in SUPPORTED:
        return {"error": "model %r not supported" % model}
    # ---- TODO: replace with real inference ----------------------------
    # Example pattern (placeholder):
    #   import onnxruntime as ort
    #   sess = ort.InferenceSession(f"models/{model}.onnx")
    #   ...
    return {
        "echo": {"model": model, "task": task},
        "hint": "Replace dispatch() with real ONNX inference.",
    }


def main():
    line = sys.stdin.readline()
    if not line.strip():
        sys.stdout.write(json.dumps({"ok": False, "error": "empty stdin"}))
        return 1
    try:
        req = json.loads(line)
    except json.JSONDecodeError as e:
        sys.stdout.write(json.dumps({"ok": False, "error": "bad json: %s" % e}))
        return 1
    t0 = time.time()
    outputs = dispatch(req)
    elapsed = time.time() - t0
    resp = {
        "ok": True,
        "id": req.get("id"),
        "model": req.get("model"),
        "task": req.get("task"),
        "elapsed_sec": round(elapsed, 3),
        "outputs": outputs,
    }
    sys.stdout.write(json.dumps(resp, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())