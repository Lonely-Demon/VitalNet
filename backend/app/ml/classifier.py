"""
VitalNet Classifier Interface — Enhanced classifier only.
Legacy classifier paths removed (triage_classifier.pkl deleted in cleanup sprint).
If loading fails, raises RuntimeError with a descriptive message.
"""
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

logger = logging.getLogger("vitalnet")

if TYPE_CHECKING:
    from app.ml.enhanced_classifier import EnhancedTriageClassifier

# Model path — enhanced classifier sits alongside this file under app/ml/models/
ENHANCED_PKL_PATH = Path(__file__).parent / "models" / "enhanced_triage_classifier.pkl"
EXPECTED_ENHANCED_PKL_SHA256 = "256db22348dc6bfcbde20bcddd079eff50a8613f86747f8e3d13572c53cde420"

# Global classifier state
_classifier: "EnhancedTriageClassifier | None" = None
_classifier_type: str | None = None
_model_info: Dict[str, Any] = {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_classifier() -> bool:
    """
    Load the enhanced multi-stage classifier.
    Catches all exceptions, logs a warning/error, sets globals to None, and returns False.
    """
    global _classifier, _classifier_type, _model_info

    try:
        if not ENHANCED_PKL_PATH.exists():
            raise FileNotFoundError(
                f"Enhanced classifier not found at {ENHANCED_PKL_PATH}. "
                "Run backend/scripts/retrain_and_export.py to regenerate."
            )

        if _sha256(ENHANCED_PKL_PATH) != EXPECTED_ENHANCED_PKL_SHA256:
            raise RuntimeError(
                f"Enhanced classifier integrity check failed for {ENHANCED_PKL_PATH}. "
                "Regenerate the model artifacts before startup."
            )

        from app.ml.enhanced_classifier import EnhancedTriageClassifier
        _classifier = EnhancedTriageClassifier.load_model(str(ENHANCED_PKL_PATH))
        _classifier_type = "enhanced"
        _model_info = _classifier.get_model_info()

        if _model_info.get("model_version") != "2.0.0":
            raise RuntimeError(
                f"Model version mismatch: expected 2.0.0, got {_model_info.get('model_version')}."
            )

        acc = _model_info["performance_metrics"].get("accuracy", "N/A")
        recall = _model_info["performance_metrics"].get("emergency_recall", "N/A")
        logger.info(
            "Enhanced classifier loaded",
            extra={
                "model_version": _model_info["model_version"],
                "accuracy": acc,
                "emergency_recall": recall,
            },
        )
        return True

    except Exception as e:
        logger.error(
            "[CRITICAL WARNING] Enhanced classifier load failed: %s. "
            "Gracefully degrading to rule-based triage fallback.",
            e,
            exc_info=True
        )
        _classifier_type = None
        _classifier = None
        _model_info = {}
        return False


def _predict_fallback(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Robust rules-based clinical triage engine for ML fallback.
    Analyzes spo2, heart_rate, bp_systolic, temperature, and symptoms.
    """
    from app.ml.model_contract import SYMPTOM_NORMALIZATION_MAP

    spo2 = form_data.get("spo2")
    heart_rate = form_data.get("heart_rate")
    bp_systolic = form_data.get("bp_systolic")
    temperature = form_data.get("temperature")
    symptoms = form_data.get("symptoms") or []

    def to_float(val):
        if val is None or val == -1 or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    spo2_f = to_float(spo2)
    hr_f = to_float(heart_rate)
    bp_sys_f = to_float(bp_systolic)
    temp_f = to_float(temperature)

    # Normalize symptoms to canonical forms
    normalized_symptoms = []
    for s in symptoms:
        raw = str(s or "").strip().lower()
        if not raw:
            continue
        cleaned = raw.replace("_", " ").replace("/", " ").replace("-", " ")
        cleaned = "".join(char for char in cleaned if char.isalnum() or char.isspace())
        cleaned = " ".join(cleaned.split())
        canonical = SYMPTOM_NORMALIZATION_MAP.get(cleaned, cleaned.replace(" ", "_"))
        normalized_symptoms.append(canonical)

    triage_level = "ROUTINE"
    risk_factors = []

    # Check emergency and urgent limits
    # 1. SpO2
    if spo2_f is not None:
        if spo2_f < 90:
            triage_level = "EMERGENCY"
            risk_factors.append(f"critically low oxygen saturation ({spo2_f:.1f}%)")
        elif spo2_f < 94:
            if triage_level == "ROUTINE":
                triage_level = "URGENT"
            risk_factors.append(f"low oxygen saturation ({spo2_f:.1f}%)")

    # 2. Heart Rate
    if hr_f is not None:
        if hr_f > 140 or hr_f < 40:
            triage_level = "EMERGENCY"
            risk_factors.append(f"critically abnormal heart rate ({hr_f:.1f} bpm)")
        elif hr_f > 130 or hr_f < 50:
            triage_level = "EMERGENCY"
            risk_factors.append(f"critically abnormal heart rate ({hr_f:.1f} bpm)")
        elif hr_f > 110 or hr_f < 60:
            if triage_level == "ROUTINE":
                triage_level = "URGENT"
            risk_factors.append(f"abnormal heart rate ({hr_f:.1f} bpm)")

    # 3. Blood Pressure (systolic)
    if bp_sys_f is not None:
        if bp_sys_f < 80 or bp_sys_f > 200:
            triage_level = "EMERGENCY"
            risk_factors.append(f"critically abnormal blood pressure ({bp_sys_f:.1f} mmHg)")
        elif bp_sys_f < 90 or bp_sys_f > 180:
            triage_level = "EMERGENCY"
            risk_factors.append(f"critically abnormal blood pressure ({bp_sys_f:.1f} mmHg)")
        elif bp_sys_f < 100 or bp_sys_f > 150:
            if triage_level == "ROUTINE":
                triage_level = "URGENT"
            risk_factors.append(f"abnormal blood pressure ({bp_sys_f:.1f} mmHg)")

    # 4. Temperature
    if temp_f is not None:
        if temp_f > 40.0:
            triage_level = "EMERGENCY"
            risk_factors.append(f"critically high fever ({temp_f:.1f}°C)")
        elif temp_f < 35.0:
            triage_level = "EMERGENCY"
            risk_factors.append(f"dangerously low temperature ({temp_f:.1f}°C)")
        elif temp_f > 38.5:
            if triage_level == "ROUTINE":
                triage_level = "URGENT"
            risk_factors.append(f"high fever ({temp_f:.1f}°C)")
        elif temp_f < 36.0:
            if triage_level == "ROUTINE":
                triage_level = "URGENT"
            risk_factors.append(f"low temperature ({temp_f:.1f}°C)")

    # 5. Symptoms
    emergency_symptoms = {"chest_pain", "altered_consciousness", "severe_bleeding", "seizure", "anaphylaxis", "stroke"}
    urgent_symptoms = {"breathlessness", "high_fever", "severe_abdominal_pain", "persistent_vomiting", "weakness_one_side", "difficulty_speaking", "swelling_face_throat", "acute_abdomen"}

    for s in normalized_symptoms:
        if s in emergency_symptoms:
            triage_level = "EMERGENCY"
            risk_factors.append(s.replace("_", " "))
        elif s in urgent_symptoms:
            if triage_level == "ROUTINE":
                triage_level = "URGENT"
            risk_factors.append(s.replace("_", " "))

    if risk_factors:
        risk_driver = "Primary risk factors: " + "; ".join(risk_factors) + f". Classified as {triage_level}."
    else:
        risk_driver = f"Multiple clinical indicators contributed to this triage decision. Classified as {triage_level}."

    probabilities = {
        "ROUTINE": 0.0,
        "URGENT": 0.0,
        "EMERGENCY": 0.0
    }
    probabilities[triage_level] = 1.0

    return {
        "triage_level": triage_level,
        "confidence_score": 1.0,
        "risk_driver": risk_driver,
        "model_version": "degraded-rules-v1.0",
        "feature_schema_version": "v45-2026-03-30",
        "processing_time": "fallback-rules",
        "uncertainty": {
            "agreement_score": 1.0,
            "epistemic_uncertainty": 0.0,
            "total_entropy": 0.0,
            "high_uncertainty": False
        },
        "probabilities": probabilities,
        "fast_path": True,
        "needs_review": triage_level in {"EMERGENCY", "URGENT"}
    }



def predict_triage(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run triage prediction using the loaded enhanced classifier.
    If the classifier is not loaded, gracefully degrades to rules-based fallback.

    Args:
        form_data: Patient data dictionary

    Returns:
        Dictionary with triage_level, confidence_score, risk_driver, and metadata
    """
    global _classifier_type, _classifier
    if _classifier_type is None or _classifier is None:
        return _predict_fallback(form_data)

    return _predict_enhanced(form_data)


def _predict_enhanced(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run prediction using the enhanced classifier."""
    try:
        if _classifier is None:
            raise RuntimeError("Enhanced classifier not initialized")

        result = _classifier.predict(form_data)

        # Extract risk driver from clinical features
        clinical_features = result.get("clinical_features", {})
        risk_driver = _generate_risk_explanation(
            result["triage_level"], clinical_features, form_data
        )

        return {
            "triage_level": result["triage_level"],
            "confidence_score": result["confidence"],
            "risk_driver": risk_driver,
            "model_version": result.get("model_version", "N/A"),
            "feature_schema_version": result.get("feature_schema_version", "N/A"),
            "processing_time": result.get("processing_time", "standard"),
            "uncertainty": result.get("uncertainty", {}),
            "probabilities": result.get("probabilities", {}),
            "fast_path": result.get("fast_path", False),
            "needs_review": result.get("needs_review", False),
        }

    except Exception as e:
        logger.error("Enhanced prediction failed: %s", e, exc_info=True)
        raise  # Let main.py's handler catch this as a 500


def _generate_risk_explanation(
    triage_level: str, clinical_features: Dict[str, float], form_data: Dict[str, Any]
) -> str:
    """
    Generate a human-readable risk explanation from enhanced classifier features.
    """
    try:
        # Find the most significant clinical indicators
        high_risk_features = {}

        # Check vital sign abnormalities
        if clinical_features.get("cardiac_risk_score", 0) >= 3.0:
            high_risk_features["Cardiac risk"] = clinical_features["cardiac_risk_score"]
        if clinical_features.get("respiratory_distress_score", 0) >= 2.0:
            high_risk_features["Respiratory distress"] = clinical_features[
                "respiratory_distress_score"
            ]
        if clinical_features.get("hemodynamic_instability", 0) >= 2.0:
            high_risk_features["Hemodynamic instability"] = clinical_features[
                "hemodynamic_instability"
            ]
        if clinical_features.get("sepsis_risk_score", 0) >= 2.0:
            high_risk_features["Sepsis risk"] = clinical_features["sepsis_risk_score"]

        # Check specific vitals
        spo2 = form_data.get("spo2", 97)
        hr = form_data.get("heart_rate", 75)
        bp_sys = form_data.get("bp_systolic", 120)
        temp = form_data.get("temperature", 37.0)

        vital_explanations = []
        if spo2 and spo2 < 90:
            vital_explanations.append(f"critically low oxygen saturation ({spo2}%)")
        elif spo2 and spo2 < 94:
            vital_explanations.append(f"low oxygen saturation ({spo2}%)")

        if hr and hr > 130:
            vital_explanations.append(f"very high heart rate ({hr} bpm)")
        elif hr and hr < 50:
            vital_explanations.append(f"very low heart rate ({hr} bpm)")

        if bp_sys and bp_sys > 180:
            vital_explanations.append(f"very high blood pressure ({bp_sys} mmHg)")
        elif bp_sys and bp_sys < 90:
            vital_explanations.append(f"low blood pressure ({bp_sys} mmHg)")

        if temp and temp > 40.0:
            vital_explanations.append(f"very high fever ({temp}°C)")
        elif temp and temp < 35.0:
            vital_explanations.append(f"dangerously low temperature ({temp}°C)")

        # Check symptom combinations
        symptoms = form_data.get("symptoms", [])
        symptom_explanations = []

        if "altered_consciousness" in symptoms:
            symptom_explanations.append("altered consciousness")
        if "severe_bleeding" in symptoms:
            symptom_explanations.append("severe bleeding")
        if "seizure" in symptoms:
            symptom_explanations.append("seizure activity")
        if "chest_pain" in symptoms and "breathlessness" in symptoms:
            symptom_explanations.append("chest pain with difficulty breathing")
        elif "chest_pain" in symptoms:
            symptom_explanations.append("chest pain")
        elif "breathlessness" in symptoms:
            symptom_explanations.append("difficulty breathing")

        # Build explanation
        explanation_parts = []

        if vital_explanations:
            explanation_parts.append(
                "vital signs showed " + ", ".join(vital_explanations[:2])
            )

        if symptom_explanations:
            explanation_parts.append(
                "patient presented with " + ", ".join(symptom_explanations[:2])
            )

        if high_risk_features:
            top_risk = max(high_risk_features.items(), key=lambda x: x[1])
            explanation_parts.append(
                f"{top_risk[0].lower()} was significantly elevated"
            )

        if explanation_parts:
            base_explanation = "Primary risk factors: " + "; ".join(
                explanation_parts[:3]
            )
        else:
            base_explanation = (
                "Multiple clinical indicators contributed to this triage decision"
            )

        return f"{base_explanation}. Classified as {triage_level}."

    except Exception as e:
        logger.warning("Risk explanation generation failed: %s", e)
        return f"Advanced clinical analysis classified this case as {triage_level}."


def get_classifier_info() -> Dict[str, Any]:
    """Get information about the currently loaded classifier."""
    return {
        "classifier_type": _classifier_type,
        "model_info": _model_info,
        "is_enhanced": _classifier_type == "enhanced",
    }


# Backwards-compatible alias
run_triage = predict_triage
