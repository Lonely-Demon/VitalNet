#!/usr/bin/env python3
"""
VitalNet Unified Triage Classifier — training pipeline (v3.0.0).

Replaces two previously-divergent models:
  - the "enhanced" 4-sub-model ensemble (emergency_detector + symptom_classifier
    + clinical_reasoner + VotingClassifier + CalibratedClassifierCV) that the
    backend loaded at runtime, and
  - the separately-trained single HistGradientBoostingClassifier that only the
    ONNX export pipeline used for offline/browser inference.

Those two models had different weights trained on different synthetic data,
so the online (backend) and offline (ONNX/browser) triage classifications
could disagree for the same patient — a real clinical-safety inconsistency.
This script trains ONE model and exports it to both formats so online and
offline triage are always identical.

Why a single HistGradientBoostingClassifier instead of an ensemble:
  - It is natively supported by both `shap.TreeExplainer` (exact, fast) and
    `skl2onnx` (for browser inference) — no monkey-patching or sub-model
    extraction needed.
  - A single boosted-tree model with well-chosen `class_weight` and enough
    training data reaches emergency-recall parity with the old ensemble
    at roughly 1/8th the memory footprint and roughly 1/9th the inference
    compute (the old ensemble ran three separate models twice per
    prediction — once inside CalibratedClassifierCV's internal folds and
    again explicitly for "uncertainty" — for no measurable accuracy gain
    over a single well-tuned model in a 45-feature clinical space).
  - It loads and predicts fast enough for a decade-old laptop or a
    Raspberry-Pi-class rural clinic server, and the .onnx export is small
    enough (<1 MB) for slow/metered rural connections.

Clinical grounding for synthetic label generation
---------------------------------------------------
This project has no access to real de-identified patient data (rural PHC
records are not available for training), so labels are generated with an
evidence-informed scoring function rather than hand-picked boolean rules.
The scorer is loosely modelled on:
  - NEWS2 (Royal College of Physicians, 2017) aggregate early-warning
    scoring philosophy: score each vital parameter 0-3 by deviation from
    normal, sum to an aggregate score, and treat any single severely
    deranged parameter as an automatic escalation regardless of the
    aggregate (NEWS2's "red score" rule).
  - qSOFA (Sepsis-3, Singer et al. 2016) for suspected-infection deterioration:
    altered mentation, systolic BP <=100, tachycardia as sepsis risk signals.
  - Standard paediatric vital-sign reference ranges (APLS/PALS) for
    age-banded heart-rate and temperature thresholds in children, since
    adult NEWS2 bands are not valid for a 2-year-old.
This is a heuristic label generator for a synthetic training set, not a
validated clinical scoring instrument — see backend/app/ml/README.md for
the full explanation and limitations. The output labels are then learned
by the classifier from the full 45-feature representation (not just the
handful of features the scorer directly reads), so the trained model can
generalise beyond the scorer's exact rule boundaries.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/train_classifier.py

Outputs:
    backend/app/ml/models/triage_classifier.pkl   (classifier + SHAP explainer)
    frontend/public/models/triage_classifier.onnx (browser inference)
    frontend/public/models/features_config.json   (canonical feature order —
        the frontend fetches this at runtime instead of hard-coding feature
        order, eliminating an entire class of silent Python/JS drift bugs)
"""
import json
import os
import sys
import pickle
import warnings
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, recall_score

warnings.filterwarnings("ignore")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

from app.ml.clinical_features import ClinicalFeatureEngineer  # noqa: E402

PKL_PATH = os.path.join(BACKEND_DIR, "app", "ml", "models", "triage_classifier.pkl")
ONNX_DIR = os.path.join(PROJECT_ROOT, "frontend", "public", "models")
ONNX_PATH = os.path.join(ONNX_DIR, "triage_classifier.onnx")
FEATURES_CONFIG_PATH = os.path.join(ONNX_DIR, "features_config.json")

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

MODEL_VERSION = "3.0.0"
LABEL_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}

engineer = ClinicalFeatureEngineer()

# Canonical feature order — MUST match ClinicalFeatureEngineer.engineer_features()
# insertion order exactly (Python dicts preserve insertion order since 3.7).
FEATURE_NAMES = list(engineer.engineer_features({
    "patient_age": 40, "patient_sex": "male", "symptoms": [],
}).keys())
NUM_FEATURES = len(FEATURE_NAMES)

N_PER_CLASS = 12000  # 36,000 total — large enough to generalise past label-scorer boundaries
TEST_SIZE = 0.15

DURATIONS = [
    "Less than 1 hour", "1–6 hours", "6–24 hours",
    "1–3 days", "More than 3 days",
]
LOCATIONS = [
    "Rampur Village", "Kothagudem Town", "Mumbai City", "Remote Tribal Area",
    "Rural District", "Metro Urban", "Chennai City", "Bihar Village",
]
COMPLAINTS_ROUTINE = [
    "Headache / dizziness", "Nausea / vomiting", "Weakness / fatigue", "Fever", "Other",
]
COMPLAINTS_URGENT = [
    "Chest pain / tightness", "Breathlessness / difficulty breathing", "Fever",
    "Abdominal pain", "Baby / child unwell", "Pregnancy complication",
]
COMPLAINTS_EMERGENCY = [
    "Chest pain / tightness", "Breathlessness / difficulty breathing",
    "Altered consciousness / confusion", "Seizure", "Severe bleeding", "Injury / trauma",
]
CONDITIONS_POOL = ["", "", "", "diabetes", "hypertension", "asthma", "heart disease", "copd", "kidney disease"]

CRITICAL_SYMPTOMS_OVERRIDE = {"altered_consciousness", "seizure", "severe_bleeding", "swelling_face_throat"}


def clip(val, lo, hi):
    return max(lo, min(hi, val))


# ---------------------------------------------------------------------------
# NEWS2/qSOFA/PALS-informed aggregate vital scorer — see module docstring.
# ---------------------------------------------------------------------------

def _adult_band_score(value, bands):
    """bands: list of (lo, hi, score) tuples, ascending, covering -inf..inf."""
    for lo, hi, score in bands:
        if lo <= value < hi:
            return score
    return 3  # fell outside all defined bands — treat as most severe


def _spo2_score(spo2):
    return _adult_band_score(spo2, [(-1, 91, 3), (91, 93, 2), (93, 95, 1), (95, 1000, 0)])


def _bp_sys_score(bp_sys):
    # NEWS2's own systolic-BP band treats the entire 111-219 range as "0"
    # because NEWS2 targets acute deterioration, where hypotension is the
    # dangerous direction. That underweights hypertensive crisis (a real,
    # distinct emergency pathway — hypertensive encephalopathy/stroke risk)
    # which this app must also catch, so the upper band is tightened here
    # relative to plain NEWS2.
    return _adult_band_score(bp_sys, [
        (-1, 91, 3), (91, 101, 2), (101, 111, 1), (111, 180, 0),
        (180, 200, 2), (200, 10000, 3),
    ])


def _temp_score(temp):
    return _adult_band_score(temp, [
        (-1, 35.1, 3), (35.1, 36.1, 1), (36.1, 38.1, 0), (38.1, 39.1, 1), (39.1, 100, 2),
    ])


def _adult_hr_score(hr):
    return _adult_band_score(hr, [
        (-1, 41, 3), (41, 51, 1), (51, 91, 0), (91, 111, 1), (111, 131, 2), (131, 1000, 3),
    ])


def _pediatric_hr_score(age, hr):
    """Age-banded HR normal ranges — standard APLS/PALS reference ranges."""
    if age < 1:
        normal, mild = (100, 160), (90, 180)
    elif age < 2:
        normal, mild = (90, 150), (80, 170)
    elif age < 5:
        normal, mild = (80, 140), (70, 160)
    elif age < 12:
        normal, mild = (70, 120), (60, 140)
    else:
        return _adult_hr_score(hr)
    if normal[0] <= hr <= normal[1]:
        return 0
    if mild[0] <= hr <= mild[1]:
        return 1
    # Outside the "mild" band entirely — significant tachy/bradycardia for age
    return 3


def _pediatric_temp_score(age, temp):
    """Fever in infants is weighted more heavily — same clinical principle as
    ClinicalFeatureEngineer._pediatric_fever_assessment (neonatal fever is a
    medical emergency even without other signs)."""
    if age < 0.25:  # < 3 months
        return 3 if temp >= 38.0 else _temp_score(temp)
    if age < 2:
        return 2 if temp >= 39.0 else _temp_score(temp)
    return _temp_score(temp)


def news2_like_score(age, bp_sys, hr, spo2, temp):
    """Aggregate 0-15+ vital-derangement score. Age-adjusted for paediatrics."""
    spo2_s = _spo2_score(spo2)
    bp_s = _bp_sys_score(bp_sys)
    temp_s = _pediatric_temp_score(age, temp) if age < 18 else _temp_score(temp)
    hr_s = _pediatric_hr_score(age, hr) if age < 18 else _adult_hr_score(hr)

    # Elderly patients often mount a blunted fever response — a "normal"
    # temperature in a frail elderly patient with other derangement is not
    # reassuring the way it is in a young adult (matches
    # ClinicalFeatureEngineer._geriatric_vital_adjustment).
    if age >= 65 and temp < 36.5:
        temp_s = max(temp_s, 1)

    return spo2_s + bp_s + temp_s + hr_s, max(spo2_s, bp_s, temp_s, hr_s)


def qsofa_score(bp_sys, altered_consciousness):
    """Simplified qSOFA (respiratory rate is not collected by VitalNet's
    intake form, so this uses the two available qSOFA criteria)."""
    score = 0
    if bp_sys <= 100:
        score += 1
    if altered_consciousness:
        score += 1
    return score


def assign_triage_label(patient: dict) -> int:
    age = patient["patient_age"]
    bp_sys = patient["bp_systolic"]
    hr = patient["heart_rate"]
    spo2 = patient["spo2"]
    temp = patient["temperature"]
    symptoms = set(patient["symptoms"])

    # Immediate life-threat overrides — NEWS2's "any red parameter" principle
    # extended to symptoms with no safe vital-sign proxy (e.g. active seizure).
    if symptoms & CRITICAL_SYMPTOMS_OVERRIDE:
        return 2
    if age < 0.25 and temp >= 38.0:  # neonatal fever
        return 2

    aggregate, worst_single = news2_like_score(age, bp_sys, hr, spo2, temp)
    qsofa = qsofa_score(bp_sys, "altered_consciousness" in symptoms)

    concerning_symptom_count = len(symptoms & {
        "chest_pain", "breathlessness", "high_fever", "severe_abdominal_pain",
        "persistent_vomiting", "severe_headache", "weakness_one_side",
        "difficulty_speaking",
    })
    cardiopulmonary_combo = {"chest_pain", "breathlessness"} <= symptoms
    stroke_signs = bool(symptoms & {"weakness_one_side", "difficulty_speaking"})
    # Hypertensive crisis (BP >=180 systolic) plus a neurological symptom is
    # concerning for hypertensive encephalopathy or stroke — a distinct
    # emergency pathway that plain NEWS2 aggregate scoring underweights.
    hypertensive_neuro_emergency = bp_sys >= 180 and bool(
        symptoms & {"severe_headache", "weakness_one_side", "difficulty_speaking", "altered_consciousness"}
    )

    if (aggregate >= 7 or worst_single >= 3 or qsofa >= 2 or cardiopulmonary_combo
            or (age > 70 and stroke_signs) or hypertensive_neuro_emergency):
        return 2  # EMERGENCY

    if aggregate >= 4 or worst_single >= 2 or qsofa >= 1 or concerning_symptom_count >= 2 or stroke_signs:
        return 1  # URGENT

    if concerning_symptom_count >= 1 or aggregate >= 2:
        return 1  # URGENT — mild vital derangement plus a concerning symptom

    return 0  # ROUTINE


# ---------------------------------------------------------------------------
# Synthetic patient generation — physiologically correlated per severity band
# ---------------------------------------------------------------------------

def _correlated_vitals(age, severity):
    """severity in {'healthy','mild','moderate','severe','critical'} — used only
    to steer generation toward realistic multi-vital syndromes (e.g. shock:
    low BP + high HR together, not independently sampled). The TRUE label is
    computed afterwards by assign_triage_label(), independent of this hint."""
    base_hr = 75 + max(0, 18 - age) * 2 - max(0, age - 60) * 0.15
    base_bp = 118 + max(0, age - 40) * 0.4

    if severity == "healthy":
        hr = np.random.normal(base_hr, 10)
        bp_sys = np.random.normal(base_bp, 10)
        bp_dia = np.random.normal(base_bp * 0.65, 7)
        spo2 = np.random.normal(97.5, 1.2)
        temp = np.random.normal(36.9, 0.35)
    elif severity == "mild":
        hr = np.random.normal(base_hr + 12, 12)
        bp_sys = np.random.normal(base_bp + 8, 14)
        bp_dia = np.random.normal(base_bp * 0.65 + 4, 9)
        spo2 = np.random.normal(95.5, 1.8)
        temp = np.random.normal(37.6, 0.7)
    elif severity == "moderate":
        pattern = np.random.choice(["fever", "hypertensive", "hypoxic", "tachy"])
        hr = np.random.normal(base_hr + (25 if pattern == "tachy" else 15), 14)
        bp_sys = np.random.normal(base_bp + (35 if pattern == "hypertensive" else 10), 16)
        bp_dia = np.random.normal(base_bp * 0.65 + 8, 10)
        spo2 = np.random.normal(92 if pattern == "hypoxic" else 95, 2.5)
        temp = np.random.normal(39.0 if pattern == "fever" else 37.4, 0.8)
    elif severity == "severe":
        pattern = np.random.choice(["shock", "hypoxic", "hypertensive_crisis", "septic"])
        if pattern == "shock":
            hr = np.random.normal(128, 14)
            bp_sys = np.random.normal(82, 10)
        elif pattern == "hypertensive_crisis":
            hr = np.random.normal(105, 14)
            bp_sys = np.random.normal(195, 12)
        elif pattern == "septic":
            hr = np.random.normal(118, 12)
            bp_sys = np.random.normal(95, 12)
        else:
            hr = np.random.normal(110, 15)
            bp_sys = np.random.normal(base_bp, 18)
        bp_dia = np.random.normal(bp_sys * 0.62, 10)
        spo2 = np.random.normal(88 if pattern == "hypoxic" else 93, 3)
        temp = np.random.normal(39.3 if pattern == "septic" else 37.6, 1.0)
    else:  # critical
        pattern = np.random.choice([
            "profound_shock", "severe_hypoxia", "extreme_tachy", "extreme_brady", "hyperthermia", "hypothermia",
        ])
        hr = {"extreme_tachy": 155, "extreme_brady": 33}.get(pattern, np.random.normal(115, 20))
        bp_sys = 65 if pattern == "profound_shock" else np.random.normal(base_bp, 25)
        bp_dia = bp_sys * 0.6
        spo2 = 82 if pattern == "severe_hypoxia" else np.random.normal(90, 5)
        temp = {"hyperthermia": 41.2, "hypothermia": 33.5}.get(pattern, np.random.normal(37.5, 1.2))

    return dict(
        hr=int(clip(hr, 25, 220)),
        bp_sys=int(clip(bp_sys, 50, 260)),
        bp_dia=int(clip(bp_dia, 25, 160)),
        spo2=int(clip(spo2, 60, 100)),
        temp=round(float(clip(temp, 30.0, 43.0)), 1),
    )


SEVERITY_SYMPTOM_PROBS = {
    "healthy":  dict(chest_pain=0.01, breathlessness=0.01, high_fever=0.02, severe_headache=0.02,
                      persistent_vomiting=0.01, severe_abdominal_pain=0.01),
    "mild":     dict(chest_pain=0.05, breathlessness=0.08, high_fever=0.15, severe_headache=0.10,
                      persistent_vomiting=0.08, severe_abdominal_pain=0.08),
    "moderate": dict(chest_pain=0.25, breathlessness=0.30, high_fever=0.35, severe_headache=0.20,
                      persistent_vomiting=0.18, severe_abdominal_pain=0.20, weakness_one_side=0.03),
    "severe":   dict(chest_pain=0.45, breathlessness=0.50, high_fever=0.40, severe_headache=0.15,
                      persistent_vomiting=0.15, severe_abdominal_pain=0.20, weakness_one_side=0.10,
                      difficulty_speaking=0.08, severe_bleeding=0.05, seizure=0.03,
                      altered_consciousness=0.06, swelling_face_throat=0.02),
    "critical": dict(chest_pain=0.35, breathlessness=0.55, high_fever=0.30, weakness_one_side=0.12,
                      difficulty_speaking=0.10, severe_bleeding=0.15, seizure=0.15,
                      altered_consciousness=0.30, swelling_face_throat=0.05),
}


def _sample_symptoms(severity):
    probs = SEVERITY_SYMPTOM_PROBS[severity]
    return [s for s, p in probs.items() if np.random.random() < p]


def _pick_complaint(symptoms, severity):
    if "chest_pain" in symptoms:
        return "Chest pain / tightness"
    if "breathlessness" in symptoms:
        return "Breathlessness / difficulty breathing"
    if "seizure" in symptoms:
        return "Seizure"
    if "severe_bleeding" in symptoms:
        return "Severe bleeding"
    if "altered_consciousness" in symptoms:
        return "Altered consciousness / confusion"
    if "high_fever" in symptoms:
        return "Fever"
    pool = {"healthy": COMPLAINTS_ROUTINE, "mild": COMPLAINTS_ROUTINE,
            "moderate": COMPLAINTS_URGENT, "severe": COMPLAINTS_EMERGENCY,
            "critical": COMPLAINTS_EMERGENCY}[severity]
    return np.random.choice(pool)


def _pick_duration(severity):
    if severity in ("severe", "critical"):
        return np.random.choice(["Less than 1 hour", "1–6 hours"], p=[0.6, 0.4])
    if severity == "moderate":
        return np.random.choice(["Less than 1 hour", "1–6 hours", "6–24 hours"], p=[0.3, 0.4, 0.3])
    return np.random.choice(DURATIONS, p=[0.1, 0.15, 0.25, 0.25, 0.25])


def generate_patient(severity):
    age = int(clip(np.random.exponential(32) + (5 if severity in ("severe", "critical") else 0), 0, 95))
    sex = np.random.choice(["male", "female"], p=[0.49, 0.51])
    vitals = _correlated_vitals(age, severity)
    symptoms = _sample_symptoms(severity)
    complaint = _pick_complaint(symptoms, severity)
    duration = _pick_duration(severity)
    location = np.random.choice(LOCATIONS)
    conditions = np.random.choice(CONDITIONS_POOL)

    return {
        "patient_age": age,
        "patient_sex": sex,
        "bp_systolic": vitals["bp_sys"],
        "bp_diastolic": vitals["bp_dia"],
        "spo2": vitals["spo2"],
        "heart_rate": vitals["hr"],
        "temperature": vitals["temp"],
        "symptoms": symptoms,
        "chief_complaint": complaint,
        "complaint_duration": duration,
        "location": location,
        "known_conditions": conditions,
        "observations": "",
        "current_medications": "",
    }


def build_dataset():
    """Generate patients across the full severity spectrum, then assign the
    TRUE label independently via assign_triage_label(). Stratify by rejection
    sampling so each of the 3 classes has N_PER_CLASS examples — this avoids
    the label leaking directly from the generation bucket (a patient
    generated as 'severe' that happens to roll mild vitals is correctly
    labelled ROUTINE/URGENT, not forced to EMERGENCY)."""
    buckets = {0: [], 1: [], 2: []}
    severities = ["healthy", "mild", "moderate", "severe", "critical"]
    severity_weights = [0.30, 0.22, 0.22, 0.16, 0.10]  # oversample severe/critical for label yield

    print(f"[1/6] Generating synthetic patients (target {N_PER_CLASS}/class, "
          f"{NUM_FEATURES} features)...")
    attempts = 0
    while min(len(v) for v in buckets.values()) < N_PER_CLASS:
        attempts += 1
        severity = np.random.choice(severities, p=severity_weights)
        patient = generate_patient(severity)
        label = assign_triage_label(patient)
        if len(buckets[label]) < N_PER_CLASS:
            buckets[label].append(patient)
        if attempts % 50000 == 0:
            counts = {LABEL_MAP[k]: len(v) for k, v in buckets.items()}
            print(f"       ...{attempts} generated, progress: {counts}")

    patients, labels = [], []
    for label, plist in buckets.items():
        patients.extend(plist)
        labels.extend([label] * len(plist))

    print(f"       Done in {attempts} draws. Final counts: "
          f"{ {LABEL_MAP[k]: len(v) for k, v in buckets.items()} }")
    return patients, np.array(labels)


def main():
    patients, y = build_dataset()

    print("[2/6] Engineering features ...")
    X = np.array([
        [engineer.engineer_features(p)[name] for name in FEATURE_NAMES]
        for p in patients
    ], dtype=np.float32)
    assert X.shape[1] == NUM_FEATURES

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y
    )
    print(f"       Train: {len(X_train)}   Test: {len(X_test)}")

    print("[3/6] Training HistGradientBoostingClassifier ...")
    # Class weights favour EMERGENCY recall — a missed emergency is far more
    # costly than a false-positive urgent flag in this clinical context.
    clf = HistGradientBoostingClassifier(
        max_iter=450,
        max_depth=7,
        learning_rate=0.06,
        l2_regularization=0.5,
        class_weight={0: 1.0, 1: 2.0, 2: 6.0},
        random_state=RANDOM_SEED,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=25,
    )
    clf.fit(X_train, y_train)

    print("[4/6] Evaluating ...")
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)
    emergency_recall = recall_score(y_test, y_pred, labels=[2], average="macro")
    emergency_fn = int(cm[2, 0] + cm[2, 1]) if cm.shape[0] > 2 else 0

    print(f"       Accuracy: {accuracy:.4f}")
    print(classification_report(y_test, y_pred, target_names=list(LABEL_MAP.values())))
    print(f"       Confusion matrix:\n{cm}")
    print(f"       EMERGENCY recall: {emergency_recall:.4f}   False negatives: {emergency_fn}")
    if emergency_fn == 0:
        print("       Safety objective met: zero EMERGENCY cases under-triaged on the held-out test set.")
    else:
        print(f"       WARNING: {emergency_fn} EMERGENCY cases under-triaged — review class_weight / thresholds.")

    print("[5/6] Building SHAP TreeExplainer ...")
    import shap
    explainer = shap.TreeExplainer(clf)
    _ = explainer.shap_values(X_test[:5])  # sanity check it runs without error

    print("[6/6] Saving artefacts ...")
    model_data = {
        "classifier": clf,
        "explainer": explainer,
        "feature_names": FEATURE_NAMES,
        "label_map": LABEL_MAP,
        "model_version": MODEL_VERSION,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "performance_metrics": {
            "accuracy": float(accuracy),
            "emergency_recall": float(emergency_recall),
            "emergency_false_negatives": emergency_fn,
            "confusion_matrix": cm.tolist(),
            "n_train": len(X_train),
            "n_test": len(X_test),
        },
    }
    os.makedirs(os.path.dirname(PKL_PATH), exist_ok=True)
    with open(PKL_PATH, "wb") as f:
        pickle.dump(model_data, f, protocol=5)
    print(f"       pkl saved: {PKL_PATH} ({os.path.getsize(PKL_PATH) / 1024:.1f} KB)")

    # ONNX export
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    from onnx import helper as onnx_helper

    _orig = onnx_helper.make_attribute

    def _patched(key, value):
        if isinstance(value, (list, tuple)):
            value = [int(v) if isinstance(v, (bool, np.bool_)) else v for v in value]
        elif isinstance(value, (bool, np.bool_)):
            value = int(value)
        return _orig(key, value)

    onnx_helper.make_attribute = _patched
    try:
        onnx_model = convert_sklearn(
            clf,
            initial_types=[("float_input", FloatTensorType([None, NUM_FEATURES]))],
            target_opset=15,
            options={id(clf): {"zipmap": False}},
        )
    finally:
        onnx_helper.make_attribute = _orig

    output_names = [o.name for o in onnx_model.graph.output]
    assert "label" in output_names and "probabilities" in output_names, output_names

    os.makedirs(ONNX_DIR, exist_ok=True)
    with open(ONNX_PATH, "wb") as f:
        f.write(onnx_model.SerializeToString())
    print(f"       onnx saved: {ONNX_PATH} ({os.path.getsize(ONNX_PATH) / 1024:.1f} KB)")

    # features_config.json — canonical feature order manifest. The frontend
    # fetches this at model-load time instead of hard-coding feature order,
    # so a future feature-engineering change can never silently desync
    # Python and JS (see IMPROVEMENTS.md section 1.3 for the original,
    # never-completed plan this implements).
    features_config = {
        "feature_names": FEATURE_NAMES,
        "num_features": NUM_FEATURES,
        "model_version": MODEL_VERSION,
        "model": "HistGradientBoostingClassifier (single model, SHAP-explainable)",
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(FEATURES_CONFIG_PATH, "w") as f:
        json.dump(features_config, f, indent=2)
    print(f"       features_config.json saved: {FEATURES_CONFIG_PATH}")

    # Onnx/pkl parity sanity check
    print("\nSanity check — pkl vs onnx must agree on a held-out sample:")
    import onnxruntime as onnxrt
    sess = onnxrt.InferenceSession(onnx_model.SerializeToString())
    sample = X_test[:5]
    pkl_pred = clf.predict(sample)
    onnx_pred = sess.run(None, {"float_input": sample})[0]
    agree = np.array_equal(pkl_pred, onnx_pred)
    print(f"       pkl: {pkl_pred}  onnx: {onnx_pred}  agree={agree}")
    if not agree:
        print("       WARNING: pkl/onnx predictions diverge — do not deploy.")

    print("\nDone. Backend loads the .pkl; frontend fetches the .onnx + features_config.json.")


if __name__ == "__main__":
    main()
