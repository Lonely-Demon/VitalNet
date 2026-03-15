#!/usr/bin/env python3
"""
Export the trained triage_classifier.pkl to ONNX format for
client-side inference via onnxruntime-web.

Usage:
    pip install skl2onnx onnxruntime
    python backend/scripts/export_onnx.py

Output:
    frontend/public/models/triage_classifier.onnx
"""

import os
import sys
import pickle
import warnings
import numpy as np

# Suppress sklearn version mismatch warnings (1.6.1 → 1.8.0 is safe)
warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PKL_PATH = os.path.join(PROJECT_ROOT, "backend", "models", "triage_classifier.pkl")
ONNX_DIR = os.path.join(PROJECT_ROOT, "frontend", "public", "models")
ONNX_PATH = os.path.join(ONNX_DIR, "triage_classifier.onnx")

# ---------------------------------------------------------------------------
# Load the trained model
# ---------------------------------------------------------------------------
print(f"[1/4] Loading model from {PKL_PATH}")
with open(PKL_PATH, "rb") as f:
    bundle = pickle.load(f)

classifier = bundle["classifier"]
feature_names = bundle["feature_names"]
label_map = bundle["label_map"]

print(f"       Classifier : {type(classifier).__name__}")
print(f"       Features   : {feature_names}")
print(f"       Labels     : {label_map}")

# ---------------------------------------------------------------------------
# Convert to ONNX
# ---------------------------------------------------------------------------
print("[2/4] Converting to ONNX ...")

from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx
from onnx import helper as onnx_helper, TensorProto

initial_type = [("float_input", FloatTensorType([None, len(feature_names)]))]

# ---------------------------------------------------------------------------
# Workaround: skl2onnx 1.20 has a bug where numpy booleans end up in
# TreeEnsembleClassifier int-typed attribute lists.  We monkey-patch
# onnx.helper.make_attribute to auto-cast bools→int so the protobuf
# serialisation doesn't choke.
# ---------------------------------------------------------------------------
_orig_make_attribute = onnx_helper.make_attribute


def _patched_make_attribute(key, value):
    """Cast numpy/python booleans to int inside list attributes."""
    if isinstance(value, (list, tuple)):
        value = [int(v) if isinstance(v, (bool, np.bool_)) else v for v in value]
    elif isinstance(value, (bool, np.bool_)):
        value = int(value)
    return _orig_make_attribute(key, value)


onnx_helper.make_attribute = _patched_make_attribute

try:
    onnx_model = convert_sklearn(
        classifier,
        initial_types=initial_type,
        target_opset=15,  # wide onnxruntime-web compat
        options={id(classifier): {"zipmap": False}},  # return raw array, not dict
    )
finally:
    onnx_helper.make_attribute = _orig_make_attribute  # restore

# ---------------------------------------------------------------------------
# Validate output names match what the frontend expects
# ---------------------------------------------------------------------------
output_names = [o.name for o in onnx_model.graph.output]
print(f"       ONNX outputs: {output_names}")

assert "label" in output_names, (
    f"Expected output named 'label', got {output_names}. "
    "The frontend (triageClassifier.js) depends on this name."
)
assert "probabilities" in output_names, (
    f"Expected output named 'probabilities', got {output_names}. "
    "The frontend (triageClassifier.js) depends on this name."
)

# ---------------------------------------------------------------------------
# Quick sanity check with onnxruntime
# ---------------------------------------------------------------------------
print("[3/4] Running sanity check ...")

import onnxruntime as onnxrt

sess = onnxrt.InferenceSession(onnx_model.SerializeToString())

# Dummy patient: 30-year-old male, normal vitals, no symptoms
dummy = np.array(
    [[30, 1, 120, 80, 98, 72, 98.6, 0, 0, 0, 0, 0, 0, 0]],
    dtype=np.float32,
)
onnx_out = sess.run(None, {"float_input": dummy})
predicted_label = int(onnx_out[0][0])
probabilities = onnx_out[1][0]

print(f"       Dummy input    : {dummy[0].tolist()}")
print(f"       Predicted label: {predicted_label} → {label_map[predicted_label]}")
print(f"       Probabilities  : {[round(float(p), 4) for p in probabilities]}")

# A normal-vitals, no-symptom patient should be ROUTINE (0)
if predicted_label != 0:
    print("  ⚠  WARNING: expected ROUTINE for a healthy dummy patient")

# ---------------------------------------------------------------------------
# Save the ONNX model
# ---------------------------------------------------------------------------
print(f"[4/4] Saving ONNX model to {ONNX_PATH}")
os.makedirs(ONNX_DIR, exist_ok=True)

with open(ONNX_PATH, "wb") as f:
    f.write(onnx_model.SerializeToString())

file_size_kb = os.path.getsize(ONNX_PATH) / 1024
print(f"       Done! Model size: {file_size_kb:.1f} KB")
print(f"       Frontend will serve it at /models/triage_classifier.onnx")
