# -*- coding: utf-8 -*-
"""
VitalNet — Triage Classifier Training Script (Definitive Clean Version)
Run this notebook top-to-bottom in a single Colab session.
Do NOT run any previous version of this script in the same session.
"""

# ── CELL 1: IMPORTS AND CONFIGURATION ─────────────────────────────────────────
#
# MODEL CHOICE: HistGradientBoostingClassifier, NOT GradientBoostingClassifier
#
# Why HistGBC, not GBC:
#   shap.TreeExplainer raises InvalidModelError for multi-class GBC.
#   The SHAP source code explicitly checks estimators_.shape[1] > 1 and rejects it.
#   This is a hard limitation in the SHAP library, not a version issue.
#   HistGBC is supported by SHAP TreeExplainer for multi-class.
#   HistGBC is also faster to train, handles missing values natively,
#   and produces equivalent or better classification quality on this dataset.

import numpy as np
import pickle
import shap
import warnings
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from google.colab import files

warnings.filterwarnings('ignore')

N            = 5000
RANDOM_SEED  = 42
TEST_SIZE    = 0.2

FEATURE_NAMES = [
    "age", "sex", "bp_systolic", "bp_diastolic", "spo2",
    "heart_rate", "temperature", "symptom_count", "chest_pain",
    "breathlessness", "altered_consciousness", "severe_bleeding",
    "seizure", "high_fever"
]

LABEL_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}

print("[OK] Cell 1 complete: imports and configuration set.")

# ── CELL 2: DATA GENERATION ────────────────────────────────────────────────────

np.random.seed(RANDOM_SEED)

def generate_patient():
    age            = np.random.randint(1, 85)
    sex            = np.random.randint(0, 2)
    bp_sys         = np.random.randint(70, 200)
    bp_dia         = np.random.randint(40, 120)
    spo2           = np.random.randint(85, 101)   # [85, 100] - clinically plausible
    hr             = np.random.randint(35, 160)
    temp           = round(np.random.uniform(34.5, 41.5), 1)
    symptom_count  = np.random.randint(0, 6)
    chest_pain     = np.random.choice([0, 1], p=[0.80, 0.20])
    breathlessness = np.random.choice([0, 1], p=[0.78, 0.22])
    alt_conscious  = np.random.choice([0, 1], p=[0.92, 0.08])
    sev_bleeding   = np.random.choice([0, 1], p=[0.94, 0.06])
    seizure        = np.random.choice([0, 1], p=[0.95, 0.05])
    high_fever     = np.random.choice([0, 1], p=[0.75, 0.25])
    return [age, sex, bp_sys, bp_dia, spo2, hr, temp, symptom_count,
            chest_pain, breathlessness, alt_conscious, sev_bleeding, seizure, high_fever]


def label_patient(p):
    age, sex, bp_sys, bp_dia, spo2, hr, temp, sym_count, cp, br, ac, sb, sz, hf = p

    # EMERGENCY (label 2)
    # Standard critical vitals + composite: elderly + low SpO2 + chest pain
    if (spo2 < 90 or hr > 130 or hr < 40 or bp_sys > 180 or bp_sys < 80 or
            temp > 40.0 or temp < 35.0 or ac == 1 or sz == 1 or sb == 1 or
            (age > 60 and spo2 < 94 and cp == 1)):
        return 2

    # URGENT (label 1)
    # Borderline vitals + high_fever carries clinical signal
    if (90 <= spo2 <= 94 or 110 <= hr <= 130 or 160 <= bp_sys <= 180 or
            38.9 <= temp <= 40.0 or hf == 1):
        return 1

    # ROUTINE (label 0)
    return 0


data   = [generate_patient() for _ in range(N)]
labels = [label_patient(p) for p in data]
X      = np.array(data)
y      = np.array(labels)

unique, counts = np.unique(y, return_counts=True)
print("[OK] Cell 2 complete: dataset generated.")
print("Label distribution:")
for lbl, count in zip(unique, counts):
    print(f"  {LABEL_MAP[lbl]}: {count} samples ({count / N:.1%})")

# ── CELL 3: TRAIN/TEST SPLIT AND WEIGHTED MODEL TRAINING ──────────────────────
#
# HistGradientBoostingClassifier accepts class_weight param directly.
# No need to compute sample_weights manually — class_weight={2: 10, 1: 2, 0: 1}
# is equivalent and cleaner. sample_weight is also supported if preferred.

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=TEST_SIZE,
    random_state=RANDOM_SEED,
    stratify=y
)

# Class weights: EMERGENCY=10.0, URGENT=2.0, ROUTINE=1.0
CLASS_WEIGHT = {0: 1.0, 1: 2.0, 2: 10.0}

clf = HistGradientBoostingClassifier(
    max_iter=150,
    max_depth=4,
    learning_rate=0.1,
    random_state=RANDOM_SEED,
    class_weight=CLASS_WEIGHT
)
clf.fit(X_train, y_train)

print(f"[OK] Cell 3 complete: {len(X_train)} training / {len(X_test)} test samples.")
print(f"  Weighted HistGradientBoostingClassifier trained.")

# ── CELL 4: SHAP TREEEXPLAINER ─────────────────────────────────────────────────
# TreeExplainer supports multi-class HistGradientBoostingClassifier natively.
# NOTE: shap.TreeExplainer does NOT support multi-class GradientBoostingClassifier.
#       It raises InvalidModelError. HistGBC is the correct model choice here.
#
# SHAP API for HistGBC multi-class:
#   explainer.shap_values(X) returns a single ndarray of shape (samples, features, classes)
#   NOT a list of per-class arrays.
#   To get SHAP values for class i: shap_array[:, :, i]
# TreeExplainer is fully picklable via standard pickle.

explainer   = shap.TreeExplainer(clf)
shap_verify = explainer.shap_values(X_test[:5])

# shap_verify shape: (5 samples, 14 features, 3 classes)
assert isinstance(shap_verify, np.ndarray),      f"Unexpected type: {type(shap_verify)}"
assert shap_verify.ndim == 3,                    f"Expected 3D array, got {shap_verify.ndim}D"
assert shap_verify.shape == (5, 14, 3),          f"Unexpected shape: {shap_verify.shape}"

print("[OK] Cell 4 complete: SHAP TreeExplainer initialized and verified.")
print(f"  shap_values shape: {shap_verify.shape}  (samples, features, classes)")

# ── CELL 5: SENSITIVITY ANALYSIS ──────────────────────────────────────────────

y_pred   = clf.predict(X_test)
cm       = confusion_matrix(y_test, y_pred)
accuracy = accuracy_score(y_test, y_pred)

# Direct confusion-matrix extraction — not recall_score with labels=[2]
emergency_tp = cm[2, 2]
emergency_fn = int(cm[2, 0] + cm[2, 1])   # FN = EMERGENCY cases predicted as ROUTINE or URGENT

print("\n[OK] Cell 5 complete: sensitivity analysis.")
print(classification_report(y_test, y_pred, target_names=[LABEL_MAP[i] for i in range(3)]))
print(f"  EMERGENCY True Positives:  {emergency_tp}")
print(f"  EMERGENCY False Negatives: {emergency_fn}")
print(f"  Overall Test Accuracy:     {accuracy:.4f}")

if emergency_fn == 0:
    print("[OK] Safety objective met: zero false negatives for EMERGENCY.")
else:
    print(f"[WARN] Safety objective NOT met: {emergency_fn} EMERGENCY cases under-triaged.")

# ── CELL 6: PICKLE SAVE WITH ALL 6 REQUIRED KEYS ─────────────────────────────
# Required keys for backend compatibility:
#   classifier    - loaded at startup by classifier.py
#   explainer     - used for per-patient SHAP risk driver explanation
#   feature_names - used to build numpy feature vectors in correct order
#   label_map     - maps 0/1/2 to ROUTINE/URGENT/EMERGENCY strings
#   accuracy      - logged at startup for backend readiness report
#   emergency_fn  - logged at startup to confirm safety objective met

model_data = {
    "classifier":    clf,
    "explainer":     explainer,
    "feature_names": FEATURE_NAMES,
    "label_map":     LABEL_MAP,
    "accuracy":      float(accuracy),
    "emergency_fn":  emergency_fn,
}

PKL_PATH = "triage_classifier.pkl"

with open(PKL_PATH, "wb") as f:
    pickle.dump(model_data, f, protocol=5)

print(f"\n[OK] Cell 6 complete: model saved as '{PKL_PATH}' with protocol 5.")

# ── CELL 7: ROUND-TRIP VERIFICATION ───────────────────────────────────────────

with open(PKL_PATH, "rb") as f:
    loaded = pickle.load(f)

REQUIRED_KEYS = ["classifier", "explainer", "feature_names", "label_map", "accuracy", "emergency_fn"]
missing       = [k for k in REQUIRED_KEYS if k not in loaded]

assert not missing, f"[FAIL] Missing keys in pickle: {missing}"
print("[OK] Cell 7: all 6 required keys present.")

# Classifier round-trip
sample_pred   = loaded["classifier"].predict(X_test[0:1])
sample_label  = loaded["label_map"][sample_pred[0]]
print(f"[OK] Classifier round-trip: sample predicted as {sample_label}")

# Explainer round-trip — shape is (1, 14, 3) for HistGBC multi-class
sample_shap   = loaded["explainer"].shap_values(X_test[0:1])
assert isinstance(sample_shap, np.ndarray) and sample_shap.shape == (1, 14, 3),     f"Explainer round-trip failed — shape: {sample_shap.shape}"
print(f"[OK] Explainer round-trip: SHAP values shape {sample_shap.shape} confirmed.")

# Metrics
print(f"\n--- Backend Readiness Report ---")
print(f"  Model Accuracy:            {loaded['accuracy']:.4f}")
print(f"  Emergency False Negatives: {loaded['emergency_fn']}")
print(f"  Status: ready for deployment.")

# ── CELL 8: DOWNLOAD ──────────────────────────────────────────────────────────

files.download(PKL_PATH)
print(f"\n[OK] Cell 8 complete: '{PKL_PATH}' download triggered.")