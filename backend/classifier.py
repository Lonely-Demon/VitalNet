import pickle
import numpy as np
from pathlib import Path

PKL_PATH = Path(__file__).parent / "models" / "triage_classifier.pkl"

# Loaded once at startup - not per request
_clf = None
_explainer = None
_feature_names = None
_label_map = None
_accuracy = None
_emergency_fn = None


def load_classifier():
    global _clf, _explainer, _feature_names, _label_map, _accuracy, _emergency_fn

    with open(PKL_PATH, "rb") as f:
        _model_data = pickle.load(f)

    # Direct dict access - if any key is missing, the .pkl is corrupt and
    # startup should fail loudly at KeyError, not silently degrade
    _clf          = _model_data["classifier"]
    _explainer    = _model_data["explainer"]
    _feature_names = _model_data["feature_names"]
    _label_map    = _model_data["label_map"]
    _accuracy     = _model_data["accuracy"]
    _emergency_fn = _model_data["emergency_fn"]

    print(f"[OK] Classifier loaded - accuracy: {_accuracy:.4f}, emergency_fn: {_emergency_fn}")
    return True


def _safe_vital(val):
    """Return the value if valid, -1 if missing or sentinel."""
    if val is None or val == -1:
        return -1
    return val


def predict_triage(form_data: dict) -> dict:
    """
    Run classifier and SHAP explainer.
    Returns triage_level, confidence_score, risk_driver.
    """
    if _clf is None:
        raise RuntimeError("Classifier not loaded - call load_classifier() at startup")

    symptoms = form_data.get("symptoms", [])

    features = np.array([[
        form_data.get("patient_age", -1),
        1 if form_data.get("patient_sex", "").lower() == "male" else 0,
        _safe_vital(form_data.get("bp_systolic")),
        _safe_vital(form_data.get("bp_diastolic")),
        _safe_vital(form_data.get("spo2")),
        _safe_vital(form_data.get("heart_rate")),
        _safe_vital(form_data.get("temperature")),
        len(symptoms),
        1 if "chest_pain" in symptoms else 0,
        1 if "breathlessness" in symptoms else 0,
        1 if "altered_consciousness" in symptoms else 0,
        1 if "severe_bleeding" in symptoms else 0,
        1 if "seizure" in symptoms else 0,
        1 if "high_fever" in symptoms else 0,
    ]], dtype=np.float32)

    pred          = _clf.predict(features)[0]
    triage_level  = _label_map[pred]
    proba         = _clf.predict_proba(features)[0]
    confidence    = float(np.max(proba))
    risk_driver   = _get_risk_driver(features[0], triage_level)

    return {
        "triage_level":    triage_level,
        "confidence_score": confidence,
        "risk_driver":     risk_driver,
    }


def _get_risk_driver(features: np.ndarray, triage_level: str) -> str:
    """
    Returns the single feature that most strongly drove THIS patient's classification.
    Uses per-patient SHAP values from TreeExplainer - not global feature_importances_.

    SHAP shape note: _explainer.shap_values() for HistGradientBoostingClassifier
    returns a single ndarray of shape (1, n_features, n_classes) - NOT a list.
    Index class axis as shap_array[0, :, class_idx].
    """
    try:
        class_idx  = {v: k for k, v in _label_map.items()}[triage_level]
        shap_vals  = _explainer.shap_values(features.reshape(1, -1))
        # shap_vals shape: (1, 14, 3) - index as [sample, feature, class]
        class_shap = np.abs(shap_vals[0, :, class_idx])
        top_idx    = int(np.argmax(class_shap))
        top_feat   = _feature_names[top_idx]
        top_val    = features[top_idx]

        # Format value with appropriate unit
        units = {
            "spo2": "%", "heart_rate": " bpm", "temperature": "C",
            "bp_systolic": " mmHg", "bp_diastolic": " mmHg", "age": " yrs"
        }
        unit       = units.get(top_feat, "")
        val_str    = f"{top_val:.1f}{unit}" if top_val != -1 else "not recorded"

        return f"{top_feat.replace('_', ' ').title()} ({val_str}) was the primary driver of {triage_level} classification."

    except Exception as e:
        print(f"[WARN] SHAP risk driver failed: {e} - using fallback")
        return f"Triage level {triage_level} assigned by ML classifier."


# Backwards-compatible alias - main.py imports run_triage
run_triage = predict_triage
