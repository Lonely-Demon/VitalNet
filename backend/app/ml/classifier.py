"""
VitalNet Classifier Interface.

Loads the single unified HistGradientBoostingClassifier (see
backend/scripts/train_classifier.py for training + the clinical rationale)
and exposes:
  - predict_triage() / run_triage() — main prediction entry point
  - get_classifier_info() — startup/health-check introspection

Two safety layers run on every prediction, in order:
  1. A deterministic safety-net check for unambiguous, extreme vitals or
     critical symptoms (mirrors NEWS2's "any red parameter" escalation
     principle). This guarantees EMERGENCY classification for these cases
     regardless of any residual ML model error — it does not depend on the
     classifier being correct.
  2. The trained classifier's own prediction for the nuanced multi-factor
     cases that don't hit an unambiguous threshold.
Risk drivers are generated from real SHAP (TreeExplainer) feature
attributions for the model's own predictions, translated into clinically
readable language. The safety-net path reports its own deterministic
reason instead (SHAP does not apply — it did not run).
"""
import logging
import pickle
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np

from app.ml.contraindications import check_contraindications

logger = logging.getLogger("vitalnet")

PKL_PATH = Path(__file__).parent / "models" / "triage_classifier.pkl"

# Global classifier state — populated once at startup by load_classifier()
_classifier = None
_explainer = None
_feature_names: list[str] = []
_label_map: Dict[int, str] = {}
_model_version: str = ""
_performance_metrics: Dict[str, Any] = {}

# Feature engineer singleton — built once, reused for every prediction
# (constructing it per request was pure allocation churn on the triage hot path).
_feature_engineer = None

# ── Abstention thresholds (C2) ────────────────────────────────────────────
# When the model's decision is weak, surface a low-confidence flag so the
# doctor treats the ML triage as tentative and reviews more carefully.
LOW_CONFIDENCE_PROBA = 0.55      # top-class probability below this = uncertain
LOW_CONFIDENCE_MARGIN = 0.15     # top-two probability gap below this = uncertain

# ── Safety-net override — see module docstring ────────────────────────────

CRITICAL_SYMPTOMS_OVERRIDE = {
    "altered_consciousness", "seizure", "severe_bleeding", "swelling_face_throat",
}

# ── NEWS2 "concerning single vital" floor (C1) ─────────────────────────────
# The safety net (above) escalates EXTREME single vitals straight to EMERGENCY.
# There is a milder band where a single vital is concerning (a NEWS2 single-
# parameter score of 2+) but not extreme — e.g. SpO2 91-92, HR 111-119. In that
# band the model could still output ROUTINE, which would be dangerous under-
# triage. This floor guarantees such a case is at least URGENT. It only ever
# RAISES a ROUTINE result to URGENT; it never lowers anything and never fires
# for EMERGENCY. Thresholds are intentionally simple so they mirror 1:1 in the
# frontend JS (see triageClassifier.js). Mild pediatric over-triage from the HR
# bound is an accepted, safe tradeoff (over-triage, never under-triage).


def _news2_concerning_vital(form_data: Dict[str, Any]) -> Optional[str]:
    """Return a reason if any single vital is in the NEWS2 'score >= 2'
    concerning band (but not extreme enough for the safety net), else None."""
    spo2 = form_data.get("spo2")
    if spo2 is not None and spo2 <= 92:
        return f"low oxygen saturation ({spo2}%)"

    bp_sys = form_data.get("bp_systolic")
    if bp_sys is not None and (bp_sys <= 100 or bp_sys >= 180):
        return f"concerning systolic blood pressure ({bp_sys} mmHg)"

    hr = form_data.get("heart_rate")
    if hr is not None and (hr <= 40 or hr >= 120):
        return f"concerning heart rate ({hr} bpm)"

    temp = form_data.get("temperature")
    if temp is not None and (temp <= 35.0 or temp >= 39.1):
        return f"concerning temperature ({temp}°C)"

    return None

# ── Human-readable labels for SHAP feature attributions ────────────────────

FEATURE_LABELS = {
    "age": "patient age", "sex": "patient sex",
    "bp_systolic": "systolic blood pressure", "bp_diastolic": "diastolic blood pressure",
    "spo2": "oxygen saturation (SpO2)", "heart_rate": "heart rate", "temperature": "body temperature",
    "symptom_count": "number of critical symptoms",
    "chest_pain": "chest pain", "breathlessness": "breathlessness",
    "altered_consciousness": "altered consciousness", "severe_bleeding": "severe bleeding",
    "seizure": "seizure activity", "high_fever": "high fever",
    "pulse_pressure": "pulse pressure", "mean_arterial_pressure": "mean arterial pressure",
    "shock_index": "shock index (HR/systolic BP)", "spo2_age_ratio": "oxygenation relative to age",
    "temp_deviation": "temperature deviation from normal",
    "cardiac_risk_score": "cardiac risk indicators",
    "respiratory_distress_score": "respiratory distress indicators",
    "hemodynamic_instability": "hemodynamic instability",
    "sepsis_risk_score": "sepsis risk indicators (qSOFA-like)",
    "pediatric_adjustment": "pediatric vital sign abnormality",
    "geriatric_adjustment": "geriatric vital sign abnormality",
    "pregnancy_adjustment": "pregnancy-related risk",
    "cardiopulmonary_cluster": "combined chest pain and breathlessness",
    "neurological_cluster": "combined altered consciousness and seizure",
    "hemorrhagic_cluster": "bleeding with low blood pressure",
    "infectious_cluster": "fever combined with multiple symptoms",
    "symptom_severity_score": "overall symptom severity",
    "symptom_duration_risk": "acuity of symptom onset",
    "chief_complaint_risk": "risk level of the chief complaint",
    "comorbidity_multiplier": "pre-existing conditions",
    "pediatric_fever_risk": "pediatric fever risk", "elderly_fall_risk": "elderly fall risk",
    "adult_cardiac_risk": "adult cardiac risk", "obstetric_emergency_risk": "obstetric emergency risk",
    "trauma_severity_score": "trauma severity", "mental_health_crisis": "mental health crisis indicators",
    "seasonal_risk": "seasonal disease risk",
    "geographic_risk": "geographic disease risk",
    "healthcare_accessibility": "healthcare accessibility",
}


def load_classifier() -> bool:
    """
    Load the unified triage classifier bundle (classifier + SHAP explainer).
    Raises RuntimeError with a descriptive message if loading fails —
    the app must not silently serve triage requests with no model loaded.
    """
    global _classifier, _explainer, _feature_names, _label_map, _model_version, _performance_metrics

    if not PKL_PATH.exists():
        raise RuntimeError(
            f"Triage classifier not found at {PKL_PATH}. "
            "Run backend/scripts/train_classifier.py to generate it."
        )

    try:
        with open(PKL_PATH, "rb") as f:
            bundle = pickle.load(f)

        _classifier = bundle["classifier"]
        _explainer = bundle["explainer"]
        _feature_names = bundle["feature_names"]
        _label_map = bundle["label_map"]
        _model_version = bundle.get("model_version", "unknown")
        _performance_metrics = bundle.get("performance_metrics", {})

        logger.info(
            "Triage classifier loaded",
            extra={
                "model_version": _model_version,
                "accuracy": _performance_metrics.get("accuracy"),
                "emergency_recall": _performance_metrics.get("emergency_recall"),
                "n_features": len(_feature_names),
            },
        )
        return True

    except Exception as e:
        raise RuntimeError(
            f"Triage classifier loading failed: {e}. "
            "The model file may be corrupt or built with an incompatible "
            "scikit-learn version — re-run scripts/train_classifier.py "
            "with the currently installed scikit-learn."
        ) from e


def _safety_net_check(form_data: Dict[str, Any]) -> Optional[str]:
    """
    Deterministic escalation for unambiguous, extreme presentations.
    Mirrors the label-generation override in train_classifier.py so
    training-time and inference-time safety guarantees stay aligned.
    Returns a human-readable reason string if triggered, else None.
    """
    symptoms = set(form_data.get("symptoms") or [])
    hit = symptoms & CRITICAL_SYMPTOMS_OVERRIDE
    if hit:
        readable = ", ".join(sorted(h.replace("_", " ") for h in hit))
        return f"Critical symptom present: {readable}"

    age = form_data.get("patient_age")
    temp = form_data.get("temperature")
    if age is not None and age < 0.25 and temp is not None and temp >= 38.0:
        return f"Neonatal fever (age {age * 12:.0f} months, temperature {temp}°C)"

    spo2 = form_data.get("spo2")
    if spo2 is not None and spo2 < 85:
        return f"Critically low oxygen saturation ({spo2}%)"

    hr = form_data.get("heart_rate")
    if hr is not None and (hr < 35 or hr > 170):
        return f"Extreme heart rate ({hr} bpm)"

    bp_sys = form_data.get("bp_systolic")
    if bp_sys is not None and (bp_sys < 70 or bp_sys > 220):
        return f"Extreme systolic blood pressure ({bp_sys} mmHg)"

    if bp_sys is not None and bp_sys >= 180:
        neuro_hit = symptoms & {
            "severe_headache", "weakness_one_side", "difficulty_speaking", "altered_consciousness",
        }
        if neuro_hit:
            readable = ", ".join(sorted(h.replace("_", " ") for h in neuro_hit))
            return (
                f"Hypertensive crisis (systolic BP {bp_sys} mmHg) with neurological "
                f"symptom(s): {readable} — possible hypertensive encephalopathy/stroke"
            )

    if temp is not None and (temp > 41.5 or temp < 33.0):
        return f"Extreme body temperature ({temp}°C)"

    return None


def predict_triage(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run triage prediction for a patient.

    Returns a dict with triage_level, confidence_score, risk_driver, and
    metadata. Never raises for a loaded classifier on well-formed input —
    the caller (cases.py submit_case) treats any exception as a 500.
    """
    global _feature_engineer
    if _classifier is None:
        raise RuntimeError("Classifier not loaded — call load_classifier() at startup")

    if _feature_engineer is None:
        from app.ml.clinical_features import ClinicalFeatureEngineer
        _feature_engineer = ClinicalFeatureEngineer()

    features = _feature_engineer.engineer_features(form_data)
    feature_vector = np.array(
        [[features[name] for name in _feature_names]], dtype=np.float32
    )

    # Contraindication/interaction flags (app/ml/contraindications.py) — an
    # independent, additive check that never changes the triage tier itself;
    # the caller (cases.py) folds any flag into needs_review. Computed
    # before either exit path below since it applies regardless of tier.
    contraindication_flags = check_contraindications(form_data)

    # Layer 1 — deterministic safety net: extreme presentations -> EMERGENCY,
    # independent of the model. Certain by construction, so never low-confidence.
    safety_reason = _safety_net_check(form_data)
    if safety_reason:
        return {
            "triage_level": "EMERGENCY",
            "confidence_score": 1.0,
            "risk_driver": f"Immediate escalation: {safety_reason}. Classified as EMERGENCY.",
            "model_version": _model_version,
            "safety_net_triggered": True,
            "low_confidence": False,
            "contraindication_flags": contraindication_flags,
        }

    # Layer 2 — trained model.
    proba = _classifier.predict_proba(feature_vector)[0]
    predicted_class = int(np.argmax(proba))
    triage_level = _label_map[predicted_class]
    confidence = float(proba[predicted_class])

    # Abstention flag (C2): weak decisions are surfaced as tentative.
    sorted_p = sorted(proba, reverse=True)
    margin = float(sorted_p[0] - sorted_p[1]) if len(sorted_p) > 1 else 1.0
    low_confidence = confidence < LOW_CONFIDENCE_PROBA or margin < LOW_CONFIDENCE_MARGIN

    # Layer 3 — NEWS2 concerning-vital floor (C1): never leave a concerning
    # single vital as ROUTINE. Deterministic, so it also resolves the
    # uncertainty (not low-confidence once floored on a hard rule).
    floor_reason = None
    if triage_level == "ROUTINE":
        floor_reason = _news2_concerning_vital(form_data)
        if floor_reason:
            triage_level = "URGENT"
            low_confidence = False

    risk_driver = _generate_shap_explanation(feature_vector, predicted_class, "ROUTINE" if floor_reason else triage_level, form_data)
    if floor_reason:
        risk_driver = (
            f"Escalated to URGENT by clinical safety floor: {floor_reason}. "
            f"(Model's own read was ROUTINE.)"
        )

    return {
        "triage_level": triage_level,
        "confidence_score": confidence,
        "risk_driver": risk_driver,
        "model_version": _model_version,
        "probabilities": {_label_map[i]: float(p) for i, p in enumerate(proba)},
        "safety_net_triggered": False,
        "news2_floor_triggered": bool(floor_reason),
        "low_confidence": low_confidence,
        "contraindication_flags": contraindication_flags,
    }


def _generate_shap_explanation(
    feature_vector: np.ndarray, predicted_class: int, triage_level: str, form_data: Dict[str, Any]
) -> str:
    """
    Generate a per-patient risk explanation from real SHAP feature
    attributions for the model's predicted class. Falls back to a generic
    statement if SHAP computation fails for any reason — explanation
    quality must never block a triage result from being returned.
    """
    try:
        shap_values = _explainer.shap_values(feature_vector)  # shape: (1, n_features, n_classes)
        contributions = shap_values[0, :, predicted_class]

        ranked = sorted(
            zip(_feature_names, contributions),
            key=lambda kv: abs(kv[1]),
            reverse=True,
        )
        # Keep only features that meaningfully pushed toward this class
        top = [(name, val) for name, val in ranked if abs(val) > 1e-4][:3]

        if not top:
            return f"No single dominant factor identified. Classified as {triage_level}."

        # "Risk" framing only makes clinical sense for URGENT/EMERGENCY —
        # for ROUTINE, describe factors as supporting the reassuring read
        # rather than implying elevated risk.
        if triage_level == "ROUTINE":
            positive_word, negative_word = "supported a routine assessment", "raised some concern but was not decisive"
        else:
            positive_word, negative_word = "increased the assessed risk", "was a mitigating factor"

        parts = []
        for name, val in top:
            label = FEATURE_LABELS.get(name, name.replace("_", " "))
            direction = positive_word if val > 0 else negative_word
            parts.append(f"{label} ({direction})")

        explanation = "Primary factors: " + "; ".join(parts) + "."
        return f"{explanation} Classified as {triage_level}."

    except Exception as e:
        logger.warning("SHAP explanation generation failed: %s", e)
        return f"Clinical analysis classified this case as {triage_level}."


def get_classifier_info() -> Dict[str, Any]:
    """Get information about the currently loaded classifier (used by /api/health)."""
    return {
        "classifier_type": "unified" if _classifier is not None else None,
        "model_info": {
            "model_version": _model_version,
            "performance_metrics": _performance_metrics,
            "n_features": len(_feature_names),
        },
        "is_enhanced": False,  # legacy field name kept for API stability
    }


# Backwards-compatible alias — cases.py imports run_triage
run_triage = predict_triage
