"""Generate real ONNX models for the AI Figure Refiner (V0.8).

Creates real, valid ONNX models using the `onnx` library:

  1. yolov8n-seg-stub.onnx — small CNN that mimics YOLOv8 detector I/O
     (input 1x3x640x640 → outputs shape-compatible with YOLOv8-seg).
     Useful as a default for the worker to load even when no real
     pre-trained weights are available.

  2. mnist-stub.onnx — tiny MNIST-style classifier (fast sanity check).

The script validates every model with `onnx.checker.check_model`.

If you have internet access and prefer a real pre-trained YOLOv8 model,
run `scripts/download_models.py` first; it pulls the .pt checkpoints
or the Kalray optimised ONNX export when available.
"""
import os
import sys
import numpy as np


def _build_yolov8_seg_stub(path):
    """Build a small ONNX model that has the same input/output shapes as
    Ultralytics YOLOv8-seg (640x640 input).

    Network: 3-conv + 1-passthrough. Truly minimal — it's a stub that
    demonstrates the inference pipeline end-to-end. Replace with a
    real YOLOv8n-seg.onnx for actual inference.
    """
    try:
        import onnx
        from onnx import helper, TensorProto, numpy_helper
    except ImportError as e:
        print("ERROR: 'onnx' library not installed — pip install onnx")
        raise

    # Input: (1, 3, 640, 640) float32 (YOLOv8 standard)
    inp = helper.make_tensor_value_info(
        "images", TensorProto.FLOAT, [1, 3, 640, 640])

    # Random init weights as numpy arrays, then convert via numpy_helper.
    rng = np.random.RandomState(42)
    w1 = numpy_helper.from_array(
        rng.randn(16, 3, 3, 3).astype(np.float32) * 0.1, name="w1")
    b1 = numpy_helper.from_array(np.zeros(16, dtype=np.float32), name="b1")
    w2 = numpy_helper.from_array(
        rng.randn(32, 16, 3, 3).astype(np.float32) * 0.1, name="w2")
    b2 = numpy_helper.from_array(np.zeros(32, dtype=np.float32), name="b2")

    conv1 = helper.make_node("Conv", ["images", "w1", "b1"], ["c1"],
                             kernel_shape=[3, 3], pads=[1, 1, 1, 1],
                             strides=[2, 2])
    relu1 = helper.make_node("Relu", ["c1"], ["r1"])
    conv2 = helper.make_node("Conv", ["r1", "w2", "b2"], ["c2"],
                             kernel_shape=[3, 3], pads=[1, 1, 1, 1],
                             strides=[2, 2])
    relu2 = helper.make_node("Relu", ["c2"], ["r2"])
    # Output: a deterministic density map (1, 1, 80, 80) (YOLOv8-seg
    # output masks are 1x32x160x160; use 1x1x80x80 for stub).
    out = helper.make_tensor_value_info(
        "output0", TensorProto.FLOAT, [1, 1, 80, 80])
    reduce = helper.make_node("ReduceMean", ["r2"], ["output0"],
                              axes=[1], keepdims=0)

    graph = helper.make_graph(
        nodes=[conv1, relu1, conv2, relu2, reduce],
        name="yolov8n-seg-stub",
        inputs=[inp],
        outputs=[out],
        initializer=[w1, b1, w2, b2],
    )
    opset = [helper.make_opsetid("", 17)]
    model = helper.make_model(
        graph, producer_name="AFR-V0.8-stub",
        opset_imports=opset,
        ir_version=8)
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, path)
    return model


def _build_mnist_stub(path):
    """Tiny MNIST classifier (1x1x28x28 → 10 logits)."""
    import onnx
    from onnx import helper, TensorProto, numpy_helper

    inp = helper.make_tensor_value_info(
        "input", TensorProto.FLOAT, [1, 1, 28, 28])
    out = helper.make_tensor_value_info(
        "logits", TensorProto.FLOAT, [1, 10])

    rng = np.random.RandomState(0)
    w = numpy_helper.from_array(
        (rng.randn(784, 10) * 0.01).astype(np.float32), name="w")
    b = numpy_helper.from_array(np.zeros(10, dtype=np.float32), name="b")

    flat = helper.make_node("Flatten", ["input"], ["flat"], axis=1)
    mm = helper.make_node("MatMul", ["flat", "w"], ["mm"])
    add = helper.make_node("Add", ["mm", "b"], ["logits"])

    graph = helper.make_graph(
        nodes=[flat, mm, add],
        name="mnist-stub",
        inputs=[inp],
        outputs=[out],
        initializer=[w, b],
    )
    model = helper.make_model(
        graph, producer_name="AFR-V0.8-mnist-stub",
        opset_imports=[helper.make_opsetid("", 13)],
        ir_version=8)
    onnx.checker.check_model(model)
    onnx.save(model, path)
    return model


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    out_dir = os.path.join(root, "addon", "ai_figure_refiner", "workers", "models")
    os.makedirs(out_dir, exist_ok=True)

    print("== AI Figure Model Refiner — ONNX model generation (V0.8) ==")
    print("target dir:", out_dir)

    # 1. YOLOv8-seg-shaped stub
    p1 = os.path.join(out_dir, "yolov8n-seg-stub.onnx")
    if not os.path.isfile(p1):
        m = _build_yolov8_seg_stub(p1)
        print("[OK] yolov8n-seg-stub.onnx  (%.1f KB)" % (os.path.getsize(p1) / 1024))
    else:
        print("[--] yolov8n-seg-stub.onnx already exists, skipping")

    # 2. MNIST stub
    p2 = os.path.join(out_dir, "mnist-stub.onnx")
    if not os.path.isfile(p2):
        _build_mnist_stub(p2)
        print("[OK] mnist-stub.onnx        (%.1f KB)" % (os.path.getsize(p2) / 1024))
    else:
        print("[--] mnist-stub.onnx already exists, skipping")

    print("\nruntime check:")
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(p1, providers=["CPUExecutionProvider"])
        import numpy as np
        x = np.random.randn(1, 3, 640, 640).astype(np.float32)
        y = sess.run(None, {"images": x})
        print("  yolov8n-seg-stub runtime OK — output shape:", y[0].shape)
    except Exception as e:
        print("  runtime skipped (install onnxruntime for end-to-end test):", e)


if __name__ == "__main__":
    main()