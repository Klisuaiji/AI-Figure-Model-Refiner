"""Headless tests for V0.8: code review fixes + real ONNX worker."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "addon"))
sys.path.insert(0, ROOT)

# --- 1. Generate ONNX models (idempotent) ---
print("--- Step 1: ensure ONNX models exist ---")
gen_script = os.path.join(ROOT, "scripts", "generate_models.py")
ret = subprocess.run(
    [sys.executable, gen_script],
    capture_output=True, text=True, timeout=60)
print(ret.stdout)
if ret.returncode != 0:
    print("FAILED to generate models:", ret.stderr)
    sys.exit(1)

# --- 2. Run the real worker subprocess ---
print("\n--- Step 2: real ONNX worker subprocess ---")
worker_script = os.path.join(
    ROOT, "addon", "ai_figure_refiner", "workers", "afr_worker.py")

req = {
    "schema": 1,
    "id": "v0_8_test_001",
    "ts": 0.0,
    "model": "figure_seg",
    "task": "segment",
    "inputs": {},   # worker will synthesise dummy input
}
input_line = json.dumps(req) + "\n"

ret = subprocess.run(
    [sys.executable, worker_script],
    input=input_line,
    capture_output=True, text=True, timeout=120,
    cwd=os.path.dirname(worker_script))
print("--- worker stdout ---")
print(ret.stdout)
if ret.stderr:
    print("--- worker stderr ---")
    print(ret.stderr)

# parse response
resp = json.loads(ret.stdout.strip())
results = []
results.append({
    "test": "real_onnx_worker_subprocess",
    "ok": resp.get("ok"),
    "id_match": resp.get("id") == req["id"],
    "model_match": resp.get("model") == "figure_seg",
    "model_file": (resp.get("outputs") or {}).get("model_file"),
    "elapsed_sec": (resp.get("outputs") or {}).get("elapsed_sec"),
    "outputs_shape": (resp.get("outputs") or {}).get("outputs", {}).get("shape"),
})
assert resp.get("ok"), "worker reported failure: %s" % resp.get("error")
assert resp.get("id") == req["id"]
assert resp.get("model") == "figure_seg"
assert (resp.get("outputs") or {}).get("model_file") == "yolov8n-seg-stub.onnx"
assert (resp.get("outputs") or {}).get("outputs", {}).get("shape")

# --- 3. Test all 5 supported models ---
print("\n--- Step 3: worker supports all 5 models ---")
for m in ("figure_seg", "depth", "normal", "hair_dense", "refine"):
    r = {"schema": 1, "id": "m_" + m, "model": m, "task": "x", "inputs": {}}
    ret = subprocess.run(
        [sys.executable, worker_script],
        input=json.dumps(r) + "\n",
        capture_output=True, text=True, timeout=120,
        cwd=os.path.dirname(worker_script))
    resp = json.loads(ret.stdout.strip())
    out = resp.get("outputs") or {}
    results.append({
        "test": "worker_supports_" + m,
        "ok": resp.get("ok"),
        "model_file": out.get("model_file"),
        "elapsed_sec": out.get("elapsed_sec"),
    })
    assert resp.get("ok"), "model %s failed: %s" % (m, resp.get("error"))

# --- 4. Inline Blender-side: register addon, confirm operator count bump ---
# NOTE: This part needs to run under Blender's bundled Python (not the
# workbuddy venv). For an all-in-one check, run scripts/test_v0_8_blender.py.
print("\n--- Step 4: addon register sanity (Blender-side check skipped here) ---")
print("  see scripts/test_v0_8_blender.py for the in-Blender sanity check")

print(json.dumps(results, ensure_ascii=False, indent=2))
print("== PASS ==")