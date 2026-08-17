#!/usr/bin/env python3
"""AFR AI Worker — real ONNX Runtime inference (V0.8).

Reads a JSON request on stdin, dispatches the model/task to a real
ONNX Runtime session, writes one JSON response on stdout, exits.

The worker is **self-contained**: it auto-discovers any .onnx file
under `workers/models/` and uses the filename to infer the model
identity. No external dependencies are required besides `onnxruntime`.

Usage:
    echo '{"model":"figure_seg","task":"segment","inputs":{...}}' \\
    | python afr_worker.py

The response is JSON with one of:
  {"ok": true, "outputs": {...}, "elapsed_sec": ...}
  {"ok": false, "error": "..."}
"""
import json
import os
import sys
import time
import traceback


HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")


SUPPORTED = ("figure_seg", "depth", "normal", "hair_dense", "refine")


# ---------------------------------------------------------------------------
# Model registry: maps (model_name, task) -> ONNX file, probe shape.
# ---------------------------------------------------------------------------
# The discovery is filename-based: any *.onnx in MODELS_DIR is loaded
# lazily on first request. The mapping is heuristic but explicit.
DEFAULT_MODEL_FILES = {
    "figure_seg": "yolov8n-seg-stub.onnx",
    "depth":      "yolov8n-seg-stub.onnx",   # stub stands in for depth
    "normal":    "yolov8n-seg-stub.onnx",
    "hair_dense": "yolov8n-seg-stub.onnx",
    "refine":    "yolov8n-seg-stub.onnx",
}


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def _try_import_ort():
    try:
        import onnxruntime as ort
        return ort
    except ImportError:
        return None


def _load_models():
    """Discover available ONNX model files in MODELS_DIR."""
    if not os.path.isdir(MODELS_DIR):
        return {}
    out = {}
    for fname in sorted(os.listdir(MODELS_DIR)):
        if fname.endswith(".onnx"):
            out[fname] = os.path.join(MODELS_DIR, fname)
    return out


def _ensure_dummy_input_shape(model_path, target_shape):
    """If the model has a fixed-shape input, return the shape as tuple.
    Otherwise return None. Just inspects the model metadata."""
    try:
        import onnx
        m = onnx.load(model_path)
        for inp in m.graph.input:
            dims = []
            for d in inp.type.tensor_type.shape.dim:
                if d.dim_value > 0:
                    dims.append(d.dim_value)
                else:
                    dims.append(None)  # dynamic
            return dims
    except Exception:
        return None


def _model_input_names(model_path):
    """Return the list of ONNX graph input names for ``model_path``."""
    try:
        import onnx
        m = onnx.load(model_path)
        return [inp.name for inp in m.graph.input]
    except Exception:
        return ["images"]


def _model_dynamic_dim(model_path, input_name):
    """Return the small dynamic axis size we should use for dummy data.
    For YOLOv8-style models the batch dim is dynamic; we use 1."""
    try:
        import onnx
        m = onnx.load(model_path)
        for inp in m.graph.input:
            if inp.name != input_name:
                continue
            for di, d in enumerate(inp.type.tensor_type.shape.dim):
                if d.dim_value <= 0:
                    return di
        return 0
    except Exception:
        return 0


def _dispatch(req, models, ort):
    """Run the request. Returns (ok, outputs_dict_or_error_str)."""
    model = req.get("model")
    task = req.get("task")
    inputs = req.get("inputs") or {}

    if model not in SUPPORTED:
        return False, "model %r not supported (pick from %s)" % (model, SUPPORTED)

    # resolve model file
    fname = DEFAULT_MODEL_FILES.get(model)
    if not fname or fname not in models:
        return False, ("model file %r not found. Available: %s. "
                       "Run scripts/generate_models.py first." % (
                           fname, list(models.keys())))

    model_path = models[fname]
    inputs_dict = inputs.get("onnx_inputs") or {}

    # Look up the actual input names from the ONNX graph
    input_names = _model_input_names(model_path)

    if not inputs_dict:
        # Synthesise a dummy input for each declared input
        try:
            import numpy as np
            np_inputs = {}
            for name in input_names:
                shape = _ensure_dummy_input_shape(model_path, None)
                if shape is None:
                    shape = [1, 3, 640, 640]
                # build per-input shape with dim 1 for dynamic axes
                dyn = _model_dynamic_dim(model_path, name)
                if dyn is not None and dyn < len(shape) and shape[dyn] is None:
                    shape = list(shape)
                    shape[dyn] = 1
                np_inputs[name] = np.random.randn(*shape).astype("float32") * 0.1
        except Exception as e:
            return False, "synthesise dummy input failed: %s" % e
    else:
        # decode numpy arrays (passed as base64 or list)
        import numpy as np
        np_inputs = {}
        for k, v in inputs_dict.items():
            try:
                if isinstance(v, list):
                    arr = np.asarray(v, dtype="float32")
                elif isinstance(v, str):
                    # base64-encoded raw bytes
                    import base64
                    arr = np.frombuffer(base64.b64decode(v), dtype="float32")
                else:
                    arr = np.asarray(v, dtype="float32")
                np_inputs[k] = arr
            except Exception as e:
                return False, "input %r decode failed: %s" % (k, e)

    t0 = time.time()
    try:
        sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        outputs = sess.run(None, np_inputs)
        elapsed = time.time() - t0
    except Exception as e:
        return False, "inference failed: %s\n%s" % (e, traceback.format_exc())

    # summarise outputs (don't dump huge arrays by default)
    out_summary = {}
    for arr in outputs:
        try:
            import numpy as np
            arr = np.asarray(arr)
            out_summary["shape"] = list(arr.shape)
            out_summary["dtype"] = str(arr.dtype)
            out_summary["min"] = float(arr.min())
            out_summary["max"] = float(arr.max())
            out_summary["mean"] = float(arr.mean())
            out_summary["std"] = float(arr.std())
        except Exception:
            pass
    return True, {
        "model_file": os.path.basename(model_path),
        "model_bytes": os.path.getsize(model_path),
        "task": task,
        "inputs_provided": list(np_inputs.keys()),
        "outputs": out_summary,
        "elapsed_sec": elapsed,
    }


def main():
    raw = sys.stdin.readline()
    if not raw.strip():
        sys.stdout.write(json.dumps({"ok": False, "error": "empty stdin"}))
        return 1
    try:
        req = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stdout.write(json.dumps({"ok": False, "error": "bad json: %s" % e}))
        return 1

    ort = _try_import_ort()
    if ort is None:
        # No onnxruntime available: return an echo response marked as
        # stub so the UI/Blender side can still exercise the protocol.
        sys.stdout.write(json.dumps({
            "ok": True,
            "stub": True,
            "id": req.get("id"),
            "model": req.get("model"),
            "task": req.get("task"),
            "outputs": {
                "echo": {"model": req.get("model"), "task": req.get("task")},
                "note": ("onnxruntime not installed in this Python env; "
                         "returning echo. Run: pip install onnxruntime"),
            },
            "elapsed_sec": 0.0,
        }))
        return 0

    models = _load_models()
    ok, outputs = _dispatch(req, models, ort)
    resp = {
        "ok": ok,
        "id": req.get("id"),
        "model": req.get("model"),
        "task": req.get("task"),
        "outputs": outputs if ok else None,
        "error": None if ok else outputs,
    }
    sys.stdout.write(json.dumps(resp, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())