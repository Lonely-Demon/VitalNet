#!/usr/bin/env python3
"""
Retrain the VitalNet triage classifier with clinically realistic synthetic data
using the full 45-feature ClinicalFeatureEngineer pipeline.

This ensures the exported ONNX model expects the same 45-feature vector that
the frontend (triageClassifier.js) builds at inference time.

Fixes the previous model's problem: the old script trained on 14 raw features
but the frontend sends 45 engineered features, causing a shape mismatch and
silent ONNX inference failure during offline mode.

This version:
  - Generates patients per triage category with realistic profiles
  - Runs each synthetic patient through ClinicalFeatureEngineer (45 features)
  - Trains a HistGradientBoostingClassifier on the 45-feature vectors
  - Saves the .pkl in the format expected by backend/classifier.py
  - Exports the ONNX model (45-feature input) for frontend inference

Usage:
    pip install scikit-learn shap skl2onnx onnxruntime numpy
    python backend/scripts/retrain_and_export.py
"""

import os
import sys
import pickle
import warnings
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

warnings.filterwarnings("ignore")

# Add backend directory to path so we can import ClinicalFeatureEngineer
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

from clinical_features import ClinicalFeatureEngineer

PKL_PATH = os.path.join(BACKEND_DIR, "models", "triage_classifier.pkl")
ONNX_DIR = os.path.join(PROJECT_ROOT, "frontend", "public", "models")
ONNX_PATH = os.path.join(ONNX_DIR, "triage_classifier.onnx")

# 45 feature names matching the ClinicalFeatureEngineer output order
FEATURE_NAMES = [
    # Basic (14)
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
    # Vital-derived (12)
    "pulse_pressure",
    "mean_arterial_pressure",
    "shock_index",
    "spo2_age_ratio",
    "temp_deviation",
    "cardiac_risk_score",
    "respiratory_distress_score",
    "hemodynamic_instability",
    "sepsis_risk_score",
    "pediatric_adjustment",
    "geriatric_adjustment",
    "pregnancy_adjustment",
    # Symptom interaction (8)
    "cardiopulmonary_cluster",
    "neurological_cluster",
    "hemorrhagic_cluster",
    "infectious_cluster",
    "symptom_severity_score",
    "symptom_duration_risk",
    "chief_complaint_risk",
    "comorbidity_multiplier",
    # Age-specific (6)
    "pediatric_fever_risk",
    "elderly_fall_risk",
    "adult_cardiac_risk",
    "obstetric_emergency_risk",
    "trauma_severity_score",
    "mental_health_crisis",
    # Contextual (5)
    "time_of_day_risk",
    "seasonal_risk",
    "geographic_risk",
    "epidemic_alert_level",
    "healthcare_accessibility",
]

NUM_FEATURES = len(FEATURE_NAMES)  # 45

LABEL_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Feature engineer instance
engineer = ClinicalFeatureEngineer()

CRITICAL_SYMPTOMS = [
    "chest_pain",
    "breathlessness",
    "altered_consciousness",
    "severe_bleeding",
    "seizure",
    "high_fever",
]

COMPLAINTS_ROUTINE = [
    "Headache / dizziness",
    "Nausea / vomiting",
    "Weakness / fatigue",
    "Fever",
    "Other",
]
COMPLAINTS_URGENT = [
    "Chest pain / tightness",
    "Breathlessness / difficulty breathing",
    "Fever",
    "Abdominal pain",
    "Baby / child unwell",
    "Pregnancy complication",
]
COMPLAINTS_EMERGENCY = [
    "Chest pain / tightness",
    "Breathlessness / difficulty breathing",
    "Altered consciousness / confusion",
    "Seizure",
    "Severe bleeding",
    "Injury / trauma",
]

DURATIONS = [
    "Less than 1 hour",
    "1\u20136 hours",
    "6\u201324 hours",
    "1\u20133 days",
    "More than 3 days",
]

LOCATIONS = [
    "Rampur Village",
    "Kothagudem Town",
    "Mumbai City",
    "Remote Tribal Area",
    "Rural District",
    "Metro Urban",
]


def clip(val, lo, hi):
    return max(lo, min(hi, val))


def random_symptoms(prob_map):
    """Pick symptoms according to individual probabilities."""
    selected = []
    for sym, prob in prob_map.items():
        if np.random.random() < prob:
            selected.append(sym)
    return selected


def _form_data(
    age,
    sex,
    bp_sys,
    bp_dia,
    spo2,
    hr,
    temp,
    symptoms,
    complaint,
    duration,
    location,
    conditions="",
):
    """Build a form_data dict matching what ClinicalFeatureEngineer expects."""
    return {
        "patient_age": age,
        "patient_sex": sex,
        "bp_systolic": bp_sys,
        "bp_diastolic": bp_dia,
        "spo2": spo2,
        "heart_rate": hr,
        "temperature": temp,
        "symptoms": symptoms,
        "chief_complaint": complaint,
        "complaint_duration": duration,
        "location": location,
        "known_conditions": conditions,
        "observations": "",
        "current_medications": "",
    }


def form_to_feature_vector(form_data):
    """Run ClinicalFeatureEngineer and return a 45-element list in correct order."""
    feat_dict = engineer.engineer_features(form_data)
    return [feat_dict[name] for name in FEATURE_NAMES]


# ---------------------------------------------------------------------------
# Synthetic data generation -- per-category with realistic distributions
# ---------------------------------------------------------------------------


def generate_routine(n):
    """Healthy patients: normal vitals, few/no alarming symptoms."""
    records = []
    for _ in range(n):
        age = clip(int(np.random.normal(40, 18)), 1, 84)
        sex = np.random.choice(["male", "female"])
        bp_sys = clip(int(np.random.normal(120, 10)), 90, 140)
        bp_dia = clip(int(np.random.normal(78, 8)), 55, 90)
        spo2 = clip(int(np.random.normal(97, 1.5)), 95, 100)
        hr = clip(int(np.random.normal(75, 10)), 55, 100)
        temp = clip(round(np.random.normal(37.0, 0.4), 1), 36.0, 37.8)
        symptoms = []  # Routine patients: no critical symptoms
        complaint = np.random.choice(COMPLAINTS_ROUTINE)
        duration = np.random.choice(
            ["1\u20133 days", "More than 3 days", "6\u201324 hours"]
        )
        location = np.random.choice(LOCATIONS)
        conditions = np.random.choice(
            ["", "", "", "diabetes", "hypertension"], p=[0.5, 0.2, 0.1, 0.1, 0.1]
        )

        fd = _form_data(
            age,
            sex,
            bp_sys,
            bp_dia,
            spo2,
            hr,
            temp,
            symptoms,
            complaint,
            duration,
            location,
            conditions,
        )
        records.append(form_to_feature_vector(fd))
    return records


def generate_urgent(n):
    """Patients with borderline vitals or concerning but non-critical symptoms."""
    records = []
    for _ in range(n):
        age = clip(int(np.random.normal(50, 18)), 1, 84)
        sex = np.random.choice(["male", "female"])

        pattern = np.random.choice(["bp_high", "hr_high", "spo2_low", "fever", "multi"])

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
        symptom_probs = {
            "high_fever": 0.4 if temp >= 38.9 else 0.2,
            "chest_pain": 0.35,
            "breathlessness": 0.4,
            "altered_consciousness": 0.0,
            "severe_bleeding": 0.0,
            "seizure": 0.0,
        }
        symptoms = random_symptoms(symptom_probs)

        complaint = np.random.choice(COMPLAINTS_URGENT)
        duration = np.random.choice(
            ["Less than 1 hour", "1\u20136 hours", "6\u201324 hours"]
        )
        location = np.random.choice(LOCATIONS)
        conditions = np.random.choice(
            ["", "diabetes", "hypertension", "asthma", ""], p=[0.3, 0.2, 0.2, 0.1, 0.2]
        )

        fd = _form_data(
            age,
            sex,
            bp_sys,
            bp_dia,
            spo2,
            hr,
            temp,
            symptoms,
            complaint,
            duration,
            location,
            conditions,
        )
        records.append(form_to_feature_vector(fd))
    return records


def generate_emergency(n):
    """Patients with critical vitals or alarming symptoms."""
    records = []
    for _ in range(n):
        age = clip(int(np.random.normal(55, 20)), 1, 84)
        sex = np.random.choice(["male", "female"])

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

        # Emergency patients tend to have alarming symptoms
        symptom_probs = {
            "chest_pain": 0.6,
            "breathlessness": 0.65,
            "high_fever": 0.5 if temp >= 38.9 else 0.3,
            "altered_consciousness": 0.0,
            "severe_bleeding": 0.0,
            "seizure": 0.0,
        }
        symptoms = random_symptoms(symptom_probs)
        # Add pattern-specific critical symptoms
        if alt_conscious:
            symptoms.append("altered_consciousness")
        if sev_bleeding:
            symptoms.append("severe_bleeding")
        if seizure_flag:
            symptoms.append("seizure")

        complaint = np.random.choice(COMPLAINTS_EMERGENCY)
        duration = np.random.choice(["Less than 1 hour", "1\u20136 hours"])
        location = np.random.choice(LOCATIONS)
        conditions = np.random.choice(
            ["", "diabetes", "heart disease", "copd", "kidney disease"],
            p=[0.2, 0.2, 0.2, 0.2, 0.2],
        )

        fd = _form_data(
            age,
            sex,
            bp_sys,
            bp_dia,
            spo2,
            hr,
            temp,
            symptoms,
            complaint,
            duration,
            location,
            conditions,
        )
        records.append(form_to_feature_vector(fd))
    return records


# ---------------------------------------------------------------------------
# Generate balanced dataset
# ---------------------------------------------------------------------------
print(f"[1/6] Generating balanced synthetic data ({NUM_FEATURES} features) ...")

N_PER_CLASS = 2000  # 6000 total

routine_data = generate_routine(N_PER_CLASS)
urgent_data = generate_urgent(N_PER_CLASS)
emergency_data = generate_emergency(N_PER_CLASS)

data = routine_data + urgent_data + emergency_data
labels = [0] * N_PER_CLASS + [1] * N_PER_CLASS + [2] * N_PER_CLASS

X = np.array(data, dtype=np.float32)
y = np.array(labels)

assert X.shape[1] == NUM_FEATURES, f"Expected {NUM_FEATURES} features, got {X.shape[1]}"

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

# Monkey-patch to fix bool->int bug in skl2onnx 1.20
_orig = onnx_helper.make_attribute


def _patched(key, value):
    if isinstance(value, (list, tuple)):
        value = [int(v) if isinstance(v, (bool, np.bool_)) else v for v in value]
    elif isinstance(value, (bool, np.bool_)):
        value = int(value)
    return _orig(key, value)


onnx_helper.make_attribute = _patched
try:
    initial_type = [("float_input", FloatTensorType([None, NUM_FEATURES]))]
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
print("[6/6] Sanity check with full 45-feature pipeline ...")

import onnxruntime as onnxrt

sess = onnxrt.InferenceSession(onnx_model.SerializeToString())

test_cases = [
    (
        "Healthy 30M",
        _form_data(
            30,
            "male",
            120,
            78,
            98,
            72,
            37.0,
            [],
            "Headache / dizziness",
            "1\u20133 days",
            "Mumbai City",
        ),
        "ROUTINE",
    ),
    (
        "Healthy 25F",
        _form_data(
            25,
            "female",
            115,
            72,
            99,
            68,
            36.8,
            [],
            "Nausea / vomiting",
            "More than 3 days",
            "Kothagudem Town",
        ),
        "ROUTINE",
    ),
    (
        "High BP + fever",
        _form_data(
            55,
            "male",
            168,
            95,
            93,
            115,
            39.5,
            ["chest_pain", "breathlessness", "high_fever"],
            "Chest pain / tightness",
            "1\u20136 hours",
            "Rampur Village",
            "hypertension",
        ),
        "URGENT",
    ),
    (
        "Tachycardia",
        _form_data(
            45,
            "female",
            140,
            88,
            94,
            122,
            38.5,
            ["breathlessness"],
            "Breathlessness / difficulty breathing",
            "6\u201324 hours",
            "Remote Tribal Area",
        ),
        "URGENT",
    ),
    (
        "Hypoxic + chest",
        _form_data(
            70,
            "male",
            90,
            60,
            84,
            110,
            38.0,
            ["chest_pain", "breathlessness"],
            "Chest pain / tightness",
            "Less than 1 hour",
            "Rural District",
            "heart disease",
        ),
        "EMERGENCY",
    ),
    (
        "Altered mental",
        _form_data(
            60,
            "female",
            100,
            65,
            92,
            100,
            37.5,
            ["altered_consciousness"],
            "Altered consciousness / confusion",
            "Less than 1 hour",
            "Rampur Village",
        ),
        "EMERGENCY",
    ),
    (
        "Seizure child",
        _form_data(
            8,
            "male",
            100,
            65,
            96,
            140,
            40.5,
            ["seizure", "high_fever"],
            "Seizure",
            "Less than 1 hour",
            "Remote Tribal Area",
        ),
        "EMERGENCY",
    ),
]

all_pass = True
for name, fd, expected in test_cases:
    feature_vector = form_to_feature_vector(fd)
    x = np.array([feature_vector], dtype=np.float32)
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
        "\n       Some predictions didn't match expected -- review the mismatches above."
    )
    print("       (Minor mismatches may be acceptable for borderline cases.)")

print(f"\nDone. Frontend ONNX model at: {ONNX_PATH}")
print(f"     Features: {NUM_FEATURES} (matches frontend triageClassifier.js)")
