#!/usr/bin/env python3
"""
Retrain the VitalNet triage classifier with clinically realistic synthetic data.

Fixes the original model's problem: uniform-random vitals over extreme ranges
caused 76.7% of patients to be labeled EMERGENCY, and class_weight={2:10}
made the model always predict EMERGENCY.

This version:
  - Generates patients per triage category for balanced classes
  - Uses normal distributions centered on clinically plausible vitals
  - Applies moderate class weights (EMERGENCY=3x, not 10x)
  - Saves the .pkl in the same format expected by backend/classifier.py
  - Also re-exports the ONNX model for frontend inference

Usage:
    pip install scikit-learn shap skl2onnx onnxruntime numpy
    python backend/scripts/retrain_and_export.py
"""

import os
import pickle
import warnings
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

warnings.filterwarnings("ignore")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PKL_PATH = os.path.join(PROJECT_ROOT, "backend", "models", "triage_classifier.pkl")
ONNX_DIR = os.path.join(PROJECT_ROOT, "frontend", "public", "models")
ONNX_PATH = os.path.join(ONNX_DIR, "triage_classifier.onnx")

FEATURE_NAMES = [
    "age",
    "sex",
    "bp_systolic",
    "bp_diastolic",
    "spo2",
    "heart_rate",
    "temperature",
    "symptom_count",
    "chest_pain",
    "breathlessness",
    "altered_consciousness",
    "severe_bleeding",
    "seizure",
    "high_fever",
]
LABEL_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# Synthetic data generation — per-category with realistic distributions
# ---------------------------------------------------------------------------


def clip(val, lo, hi):
    return max(lo, min(hi, val))


def generate_routine(n):
    """Healthy patients: normal vitals, few/no alarming symptoms."""
    patients = []
    for _ in range(n):
        age = clip(int(np.random.normal(40, 18)), 1, 84)
        sex = np.random.randint(0, 2)
        bp_sys = clip(int(np.random.normal(120, 10)), 90, 140)
        bp_dia = clip(int(np.random.normal(78, 8)), 55, 90)
        spo2 = clip(int(np.random.normal(97, 1.5)), 95, 100)
        hr = clip(int(np.random.normal(75, 10)), 55, 100)
        temp = clip(round(np.random.normal(37.0, 0.4), 1), 36.0, 37.8)
        # Routine patients: no critical symptoms
        chest_pain = 0
        breathlessness = 0
        alt_conscious = 0
        sev_bleeding = 0
        seizure = 0
        high_fever = 0
        symptom_count = 0
        patients.append(
            [
                age,
                sex,
                bp_sys,
                bp_dia,
                spo2,
                hr,
                temp,
                symptom_count,
                chest_pain,
                breathlessness,
                alt_conscious,
                sev_bleeding,
                seizure,
                high_fever,
            ]
        )
    return patients


def generate_urgent(n):
    """Patients with borderline vitals or concerning but non-critical symptoms."""
    patients = []
    for _ in range(n):
        age = clip(int(np.random.normal(50, 18)), 1, 84)
        sex = np.random.randint(0, 2)

        # Pick 1-2 abnormal vital signs (borderline, not extreme)
        pattern = np.random.choice(["bp_high", "hr_high", "spo2_low", "fever", "multi"])

        # Start with normal-ish baselines
        bp_sys = clip(int(np.random.normal(130, 12)), 100, 175)
        bp_dia = clip(int(np.random.normal(85, 10)), 60, 100)
        spo2 = clip(int(np.random.normal(95, 2)), 90, 99)
        hr = clip(int(np.random.normal(85, 12)), 55, 125)
        temp = clip(round(np.random.normal(37.5, 0.6), 1), 36.5, 39.5)

        if pattern == "bp_high":
            bp_sys = clip(int(np.random.normal(165, 8)), 155, 180)
        elif pattern == "hr_high":
            hr = clip(int(np.random.normal(118, 8)), 105, 130)
        elif pattern == "spo2_low":
            spo2 = clip(int(np.random.normal(92, 1.5)), 90, 94)
        elif pattern == "fever":
            temp = clip(round(np.random.normal(39.2, 0.4), 1), 38.5, 40.0)
        else:  # multi
            bp_sys = clip(int(np.random.normal(155, 10)), 145, 175)
            hr = clip(int(np.random.normal(110, 8)), 100, 125)

        # May have some concerning symptoms (not the most critical)
        high_fever = 1 if temp >= 38.9 else np.random.choice([0, 1], p=[0.6, 0.4])
        chest_pain = np.random.choice([0, 1], p=[0.65, 0.35])
        breathlessness = np.random.choice([0, 1], p=[0.6, 0.4])
        alt_conscious = 0
        sev_bleeding = 0
        seizure = 0
        symptom_count = sum(
            [
                chest_pain,
                breathlessness,
                alt_conscious,
                sev_bleeding,
                seizure,
                high_fever,
            ]
        )

        patients.append(
            [
                age,
                sex,
                bp_sys,
                bp_dia,
                spo2,
                hr,
                temp,
                symptom_count,
                chest_pain,
                breathlessness,
                alt_conscious,
                sev_bleeding,
                seizure,
                high_fever,
            ]
        )
    return patients


def generate_emergency(n):
    """Patients with critical vitals or alarming symptoms."""
    patients = []
    for _ in range(n):
        age = clip(int(np.random.normal(55, 20)), 1, 84)
        sex = np.random.randint(0, 2)

        pattern = np.random.choice(
            [
                "hypotension",
                "hypertensive_crisis",
                "hypoxia",
                "extreme_tachy",
                "extreme_brady",
                "hyperthermia",
                "hypothermia",
                "altered_conscious",
                "seizure",
                "bleeding",
                "multi_critical",
            ]
        )

        # Baselines that will be overridden
        bp_sys = clip(int(np.random.normal(120, 15)), 85, 170)
        bp_dia = clip(int(np.random.normal(75, 10)), 45, 100)
        spo2 = clip(int(np.random.normal(94, 4)), 80, 99)
        hr = clip(int(np.random.normal(95, 20)), 40, 155)
        temp = clip(round(np.random.normal(37.8, 1.0), 1), 35.0, 40.0)

        alt_conscious = 0
        sev_bleeding = 0
        seizure_flag = 0

        if pattern == "hypotension":
            bp_sys = clip(int(np.random.normal(70, 8)), 50, 79)
            bp_dia = clip(int(np.random.normal(42, 6)), 30, 55)
        elif pattern == "hypertensive_crisis":
            bp_sys = clip(int(np.random.normal(195, 10)), 181, 220)
            bp_dia = clip(int(np.random.normal(110, 8)), 95, 130)
        elif pattern == "hypoxia":
            spo2 = clip(int(np.random.normal(85, 3)), 70, 89)
        elif pattern == "extreme_tachy":
            hr = clip(int(np.random.normal(145, 10)), 131, 180)
        elif pattern == "extreme_brady":
            hr = clip(int(np.random.normal(35, 3)), 25, 39)
        elif pattern == "hyperthermia":
            temp = clip(round(np.random.normal(41.0, 0.5), 1), 40.1, 42.5)
        elif pattern == "hypothermia":
            temp = clip(round(np.random.normal(34.0, 0.5), 1), 32.0, 34.9)
        elif pattern == "altered_conscious":
            alt_conscious = 1
        elif pattern == "seizure":
            seizure_flag = 1
        elif pattern == "bleeding":
            sev_bleeding = 1
        else:  # multi_critical
            spo2 = clip(int(np.random.normal(87, 3)), 78, 92)
            hr = clip(int(np.random.normal(135, 10)), 120, 160)
            bp_sys = clip(int(np.random.normal(75, 8)), 55, 85)

        chest_pain = np.random.choice([0, 1], p=[0.4, 0.6])
        breathlessness = np.random.choice([0, 1], p=[0.35, 0.65])
        high_fever = 1 if temp >= 38.9 else np.random.choice([0, 1], p=[0.5, 0.5])
        symptom_count = sum(
            [
                chest_pain,
                breathlessness,
                alt_conscious,
                sev_bleeding,
                seizure_flag,
                high_fever,
            ]
        )

        patients.append(
            [
                age,
                sex,
                bp_sys,
                bp_dia,
                spo2,
                hr,
                temp,
                symptom_count,
                chest_pain,
                breathlessness,
                alt_conscious,
                sev_bleeding,
                seizure_flag,
                high_fever,
            ]
        )
    return patients


# ---------------------------------------------------------------------------
# Generate balanced dataset
# ---------------------------------------------------------------------------
print("[1/6] Generating balanced synthetic data ...")

N_PER_CLASS = 2000  # 6000 total

routine_data = generate_routine(N_PER_CLASS)
urgent_data = generate_urgent(N_PER_CLASS)
emergency_data = generate_emergency(N_PER_CLASS)

data = routine_data + urgent_data + emergency_data
labels = [0] * N_PER_CLASS + [1] * N_PER_CLASS + [2] * N_PER_CLASS

X = np.array(data, dtype=np.float32)
y = np.array(labels)

unique, counts = np.unique(y, return_counts=True)
for lbl, cnt in zip(unique, counts):
    print(f"       {LABEL_MAP[lbl]}: {cnt} ({cnt / len(y):.1%})")

# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------
print("[2/6] Training HistGradientBoostingClassifier ...")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
)

# Moderate class weights: still favor catching emergencies, but not 10x
CLASS_WEIGHT = {0: 1.0, 1: 1.5, 2: 3.0}

clf = HistGradientBoostingClassifier(
    max_iter=200,
    max_depth=5,
    learning_rate=0.1,
    random_state=RANDOM_SEED,
    class_weight=CLASS_WEIGHT,
)
clf.fit(X_train, y_train)

y_pred = clf.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
cm = confusion_matrix(y_test, y_pred)
emergency_fn = int(cm[2, 0] + cm[2, 1])

print(f"       Accuracy: {accuracy:.4f}")
print(classification_report(y_test, y_pred, target_names=list(LABEL_MAP.values())))
print(f"       EMERGENCY false negatives: {emergency_fn}")

# ---------------------------------------------------------------------------
# SHAP explainer
# ---------------------------------------------------------------------------
print("[3/6] Building SHAP TreeExplainer ...")

import shap

explainer = shap.TreeExplainer(clf)
shap_verify = explainer.shap_values(X_test[:3])
print(f"       SHAP values shape: {shap_verify.shape}")

# ---------------------------------------------------------------------------
# Save pkl
# ---------------------------------------------------------------------------
print(f"[4/6] Saving pkl to {PKL_PATH} ...")

model_data = {
    "classifier": clf,
    "explainer": explainer,
    "feature_names": FEATURE_NAMES,
    "label_map": LABEL_MAP,
    "accuracy": float(accuracy),
    "emergency_fn": emergency_fn,
}

with open(PKL_PATH, "wb") as f:
    pickle.dump(model_data, f, protocol=5)

print(f"       Saved ({os.path.getsize(PKL_PATH) / 1024:.1f} KB)")

# ---------------------------------------------------------------------------
# ONNX export
# ---------------------------------------------------------------------------
print("[5/6] Exporting to ONNX ...")

from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from onnx import helper as onnx_helper

# Monkey-patch to fix bool→int bug in skl2onnx 1.20
_orig = onnx_helper.make_attribute


def _patched(key, value):
    if isinstance(value, (list, tuple)):
        value = [int(v) if isinstance(v, (bool, np.bool_)) else v for v in value]
    elif isinstance(value, (bool, np.bool_)):
        value = int(value)
    return _orig(key, value)


onnx_helper.make_attribute = _patched
try:
    initial_type = [("float_input", FloatTensorType([None, 14]))]
    onnx_model = convert_sklearn(
        clf,
        initial_types=initial_type,
        target_opset=15,
        options={id(clf): {"zipmap": False}},
    )
finally:
    onnx_helper.make_attribute = _orig

output_names = [o.name for o in onnx_model.graph.output]
print(f"       ONNX outputs: {output_names}")
assert "label" in output_names and "probabilities" in output_names

os.makedirs(ONNX_DIR, exist_ok=True)
with open(ONNX_PATH, "wb") as f:
    f.write(onnx_model.SerializeToString())

print(f"       ONNX model: {os.path.getsize(ONNX_PATH) / 1024:.1f} KB")

# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------
print("[6/6] Sanity check ...")

import onnxruntime as onnxrt

sess = onnxrt.InferenceSession(onnx_model.SerializeToString())

test_cases = [
    ("Healthy 30M", [30, 1, 120, 78, 98, 72, 37.0, 0, 0, 0, 0, 0, 0, 0], "ROUTINE"),
    ("Healthy 25F", [25, 0, 115, 72, 99, 68, 36.8, 0, 0, 0, 0, 0, 0, 0], "ROUTINE"),
    ("High BP + fever", [55, 1, 168, 95, 93, 115, 39.5, 3, 1, 1, 0, 0, 0, 1], "URGENT"),
    ("Tachycardia", [45, 0, 140, 88, 94, 122, 38.5, 2, 0, 1, 0, 0, 0, 0], "URGENT"),
    ("Hypoxic", [70, 1, 90, 60, 84, 110, 38.0, 2, 1, 1, 0, 0, 0, 0], "EMERGENCY"),
    (
        "Altered mental",
        [60, 0, 100, 65, 92, 100, 37.5, 1, 0, 0, 1, 0, 0, 0],
        "EMERGENCY",
    ),
    ("Seizure", [8, 1, 100, 65, 96, 140, 40.5, 2, 0, 0, 0, 0, 1, 1], "EMERGENCY"),
]

all_pass = True
for name, feats, expected in test_cases:
    x = np.array([feats], dtype=np.float32)
    out = sess.run(None, {"float_input": x})
    pred_idx = int(out[0][0])
    pred_label = LABEL_MAP[pred_idx]
    probs = [round(float(p), 3) for p in out[1][0]]
    ok = "OK" if pred_label == expected else "MISMATCH"
    if pred_label != expected:
        all_pass = False
    print(f"       {ok} {name}: {pred_label} (expected {expected}) probs={probs}")

if all_pass:
    print("\n       All sanity checks passed!")
else:
    print(
        "\n       Some predictions didn't match expected — review the mismatches above."
    )
    print("       (Minor mismatches may be acceptable for borderline cases.)")

print(f"\nDone. Frontend model at: {ONNX_PATH}")
