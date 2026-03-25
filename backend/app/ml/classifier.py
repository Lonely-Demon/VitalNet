"""
VitalNet Classifier Interface — Enhanced classifier only.
Legacy classifier paths removed (triage_classifier.pkl deleted in cleanup sprint).
If loading fails, raises RuntimeError with a descriptive message.
"""
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("vitalnet")

# Model path — enhanced classifier sits alongside this file under app/ml/models/
ENHANCED_PKL_PATH = Path(__file__).parent / "models" / "enhanced_triage_classifier.pkl"

# Global classifier state
_classifier = None
_classifier_type = None
_model_info = {}


def load_classifier() -> bool:
    """
    Load the enhanced multi-stage classifier.
    Raises RuntimeError with a descriptive message if loading fails.
    """
    global _classifier, _classifier_type, _model_info

    if not ENHANCED_PKL_PATH.exists():
        raise RuntimeError(
            f"Enhanced classifier not found at {ENHANCED_PKL_PATH}. "
            "Run backend/scripts/retrain_and_export.py to regenerate."
        )

    try:
        from app.ml.enhanced_classifier import EnhancedTriageClassifier
        _classifier = EnhancedTriageClassifier.load_model(str(ENHANCED_PKL_PATH))
        _classifier_type = "enhanced"
        _model_info = _classifier.get_model_info()

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
        raise RuntimeError(
            f"Enhanced classifier loading failed: {e}. "
            "The model file may be corrupt. Run retrain_and_export.py to regenerate."
        ) from e


def predict_triage(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run triage prediction using the loaded enhanced classifier.

    Args:
        form_data: Patient data dictionary

    Returns:
        Dictionary with triage_level, confidence_score, risk_driver, and metadata
    """
    if _classifier_type is None:
        raise RuntimeError("Classifier not loaded — call load_classifier() at startup")

    return _predict_enhanced(form_data)


def _predict_enhanced(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run prediction using the enhanced classifier."""
    try:
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
            "processing_time": result.get("processing_time", "standard"),
            "uncertainty": result.get("uncertainty", {}),
            "probabilities": result.get("probabilities", {}),
            "fast_path": result.get("fast_path", False),
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
