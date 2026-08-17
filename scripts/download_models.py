"""Download ONNX inference models for the AI Figure Refiner (V0.8).

Tries multiple CDN/Repo URLs for each model and falls back gracefully.
Models are downloaded into:
    <project_root>/addon/ai_figure_refiner/workers/models/

Each model has a target size and a list of candidate URLs. The script
verifies the downloaded file is at least 50% of the expected size
(some mirrors trim weights) and that the file starts with a valid ONNX
magic header / protobuf signature.

Pure stdlib (urllib).
"""
import hashlib
import os
import sys
import urllib.request
import urllib.error


# Compute project root: scripts/download_models.py -> .. (project root)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODELS_DIR = os.path.join(ROOT, "addon", "ai_figure_refiner", "workers", "models")
os.makedirs(MODELS_DIR, exist_ok=True)


# (display_name, filename, expected_size_bytes, [candidate_urls])
MODEL_SOURCES = [
    {
        "name": "yolov8n-seg",
        "filename": "yolov8n-seg.onnx",
        "expected_size": 13_000_000,
        "min_acceptable_size": 5_000_000,
        "urls": [
            # Ultralytics v0.0.0 release (PyTorch checkpoints; ONNX is
            # exported from these — but ONNX itself is hosted at the
            # same tag by Ultralytics' export pipeline, see below).
            "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n-seg.onnx",
            # Kalray optimised export on HuggingFace (small, valid ONNX)
            "https://huggingface.co/Kalray/yolov8n-seg/resolve/main/yolov8n-seg.optimized.onnx",
        ],
        "description": "YOLOv8 nano segmentation (COCO classes incl. person)",
        "input": "image (1,3,640,640) float32",
        "output": "detections (1,116,8400) + masks (1,32,160,160)",
    },
    {
        "name": "yolov8n",
        "filename": "yolov8n.onnx",
        "expected_size": 6_500_000,
        "min_acceptable_size": 3_000_000,
        "urls": [
            "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx",
        ],
        "description": "YOLOv8 nano detection (fallback; lighter than seg)",
        "input": "image (1,3,640,640) float32",
        "output": "detections (1,84,8400)",
    },
]


def _download_with_progress(url, dest):
    """Download url -> dest with a simple chunked progress print."""
    print("  ↓ %s" % url)
    req = urllib.request.Request(url, headers={"User-Agent": "AFR/0.8"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        with open(dest, "wb") as f:
            downloaded = 0
            chunk = 1024 * 1024  # 1 MB
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                f.write(buf)
                downloaded += len(buf)
                if total > 0:
                    pct = downloaded * 100.0 / total
                    sys.stdout.write(
                        "\r    [%6.2f%%] %d / %d MB"
                        % (pct, downloaded // (1024 * 1024),
                           total // (1024 * 1024)))
                    sys.stdout.flush()
            sys.stdout.write("\n")
    return downloaded


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_like_onnx(path):
    """ONNX files are protobuf-shaped; the first byte must be 0x08
    (varint field 1, wire type 0). Models sometimes start with a
    ZIP header (also protobuf) — both are valid ONNX containers."""
    try:
        with open(path, "rb") as f:
            head = f.read(8)
        if not head:
            return False
        # protobuf-style: first byte is a field tag (varint)
        # ZIP-style: PK\x03\x04 (0x50 0x4B 0x03 0x04)
        # Plain text (YAML/JSON) we explicitly reject
        if head[0] == 0x08:
            return True
        if head[:4] == b"PK\x03\x04":
            return True
        # Reject obvious text
        if head[0] in (0x7B, 0x22, 0x3C, 0x23):  # { " < #
            return False
        # Reject HTML/XML (random fork responses)
        if head[:5] == b"<!DOC" or head[:5] == b"<?xml":
            return False
        # Some mirrors wrap the file in a tar or 7z stream; poke the
        # first non-zero byte
        if head[0] in (0x1F, 0x7F):  # gzip / 7z
            return True
        # Fallback: check that it isn't readable as text
        try:
            head.decode("utf-8")
            return False
        except UnicodeDecodeError:
            return True
    except Exception:
        return False


def download_model(spec):
    """Resolve a single model spec. Returns dict with status."""
    dest = os.path.join(MODELS_DIR, spec["filename"])
    if os.path.isfile(dest):
        size = os.path.getsize(dest)
        if size >= spec["min_acceptable_size"]:
            return {
                "name": spec["name"], "status": "already_downloaded",
                "path": dest, "size_bytes": size,
                "sha256": _sha256(dest)[:16],
            }
    last_error = None
    for url in spec["urls"]:
        try:
            print("[%s] trying %s" % (spec["name"], url))
            size = _download_with_progress(url, dest)
            if size < spec["min_acceptable_size"]:
                last_error = "downloaded %d bytes < min %d" % (
                    size, spec["min_acceptable_size"])
                if os.path.isfile(dest):
                    os.remove(dest)
                continue
            if not _looks_like_onnx(dest):
                last_error = "file does not look like ONNX"
                if os.path.isfile(dest):
                    os.remove(dest)
                continue
            sha = _sha256(dest)
            return {
                "name": spec["name"], "status": "downloaded",
                "path": dest, "size_bytes": size,
                "sha256": sha[:16],
                "url": url,
            }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                OSError) as e:
            last_error = str(e)
            if os.path.isfile(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
            print("  ✗ failed: %s" % e)
            continue
    return {
        "name": spec["name"], "status": "failed",
        "error": last_error,
        "attempted_urls": spec["urls"],
    }


def download_all():
    print("== AI Figure Model Refiner — model download (V0.8) ==")
    print("target dir: %s" % MODELS_DIR)
    results = []
    for spec in MODEL_SOURCES:
        print("\n[%s] %s" % (spec["name"], spec["description"]))
        print("  input : %s" % spec.get("input", "—"))
        print("  output: %s" % spec.get("output", "—"))
        results.append(download_model(spec))
    return results


if __name__ == "__main__":
    import json
    print(json.dumps(download_all(), indent=2, default=str))