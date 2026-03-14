"""
VitalNet Classifier Interface
Supports both legacy and enhanced classifier systems with backward compatibility
"""

import pickle
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

# Model paths
LEGACY_PKL_PATH = Path(__file__).parent / "models" / "triage_classifier.pkl"
ENHANCED_PKL_PATH = Path(__file__).parent / "models" / "enhanced_triage_classifier.pkl"

# Global classifier state
_classifier = None
_classifier_type = None
_model_info = {}

# Legacy classifier globals (for backward compatibility)
_clf = None
_explainer = None
_feature_names = None
_label_map = None
_accuracy = None
_emergency_fn = None


def load_classifier():
    """
    Load the best available classifier (enhanced if available, otherwise legacy)
    """
    global _classifier, _classifier_type, _model_info
    global _clf, _explainer, _feature_names, _label_map, _accuracy, _emergency_fn

    # Try to load enhanced classifier first
    if ENHANCED_PKL_PATH.exists():
        try:
            print("[Classifier] Loading enhanced multi-stage classifier...")
            from enhanced_classifier import EnhancedTriageClassifier

            _classifier = EnhancedTriageClassifier.load_model(str(ENHANCED_PKL_PATH))
            _classifier_type = "enhanced"
            _model_info = _classifier.get_model_info()

            print(f"[OK] Enhanced classifier loaded - version: {_model_info['model_version']}")
            print(f"[OK] Model accuracy: {_model_info['performance_metrics'].get('accuracy', 'N/A'):.4f}")
            print(f"[OK] Emergency recall: {_model_info['performance_metrics'].get('emergency_recall', 'N/A'):.4f}")

            return True

        except Exception as e:
            print(f"[WARN] Enhanced classifier loading failed: {e}")
            print("[Classifier] Falling back to legacy classifier...")

    # Fall back to legacy classifier
    if LEGACY_PKL_PATH.exists():
        try:
            print("[Classifier] Loading legacy classifier...")

            with open(LEGACY_PKL_PATH, "rb") as f:
                _model_data = pickle.load(f)

            # Legacy classifier setup
            _clf = _model_data["classifier"]
            _explainer = _model_data["explainer"]
            _feature_names = _model_data["feature_names"]
            _label_map = _model_data["label_map"]
            _accuracy = _model_data["accuracy"]
            _emergency_fn = _model_data["emergency_fn"]

            _classifier_type = "legacy"
            _model_info = {
                'model_version': '1.0.0',
                'classifier_type': 'HistGradientBoostingClassifier',
                'accuracy': _accuracy,
                'emergency_fn': _emergency_fn
            }

            print(f"[OK] Legacy classifier loaded - accuracy: {_accuracy:.4f}, emergency_fn: {_emergency_fn}")
            return True

        except Exception as e:
            print(f"[ERROR] Legacy classifier loading failed: {e}")
            raise RuntimeError("No valid classifier found")

    else:
        raise RuntimeError("No classifier file found")


def predict_triage(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run triage prediction using the loaded classifier

    Args:
        form_data: Patient data dictionary

    Returns:
        Dictionary with triage_level, confidence_score, risk_driver, and metadata
    """
    if _classifier_type is None:
        raise RuntimeError("Classifier not loaded - call load_classifier() at startup")

    if _classifier_type == "enhanced":
        return _predict_enhanced(form_data)
    else:
        return _predict_legacy(form_data)


def _predict_enhanced(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run prediction using the enhanced classifier"""
    try:
        result = _classifier.predict(form_data)

        # Extract risk driver from clinical features
        clinical_features = result.get('clinical_features', {})
        risk_driver = _generate_risk_explanation(
            result['triage_level'],
            clinical_features,
            form_data
        )

        return {
            "triage_level": result['triage_level'],
            "confidence_score": result['confidence'],
            "risk_driver": risk_driver,
            "model_version": result.get('model_version', 'N/A'),
            "processing_time": result.get('processing_time', 'standard'),
            "uncertainty": result.get('uncertainty', {}),
            "probabilities": result.get('probabilities', {}),
            "fast_path": result.get('fast_path', False)
        }

    except Exception as e:
        print(f"[ERROR] Enhanced prediction failed: {e}")
        # Fall back to legacy prediction if available
        if _clf is not None:
            print("[Classifier] Falling back to legacy prediction...")
            return _predict_legacy(form_data)
        else:
            raise


def _predict_legacy(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run prediction using the legacy classifier"""
    if _clf is None:
        raise RuntimeError("Legacy classifier not loaded")

    symptoms = form_data.get("symptoms", [])

    features = np.array([[
        form_data.get("patient_age", -1),
        1 if form_data.get("patient_sex", "").lower() == "male" else 0,
        _safe_vital(form_data.get("bp_systolic")),
        _safe_vital(form_data.get("bp_diastolic")),
        _safe_vital(form_data.get("spo2")),
        _safe_vital(form_data.get("heart_rate")),
        _safe_vital(form_data.get("temperature")),
        len([s for s in symptoms if s in [
            'chest_pain', 'breathlessness', 'altered_consciousness',
            'severe_bleeding', 'seizure', 'high_fever'
        ]]),
        1 if "chest_pain" in symptoms else 0,
        1 if "breathlessness" in symptoms else 0,
        1 if "altered_consciousness" in symptoms else 0,
        1 if "severe_bleeding" in symptoms else 0,
        1 if "seizure" in symptoms else 0,
        1 if "high_fever" in symptoms else 0,
    ]], dtype=np.float32)

    pred = _clf.predict(features)[0]
    triage_level = _label_map[pred]
    proba = _clf.predict_proba(features)[0]
    confidence = float(np.max(proba))
    risk_driver = _get_legacy_risk_driver(features[0], triage_level)

    return {
        "triage_level": triage_level,
        "confidence_score": confidence,
        "risk_driver": risk_driver,
        "model_version": "1.0.0-legacy",
        "processing_time": "legacy",
        "fast_path": False
    }


def _generate_risk_explanation(triage_level: str, clinical_features: Dict[str, float],
                             form_data: Dict[str, Any]) -> str:
    """
    Generate a human-readable risk explanation from enhanced classifier features
    """
    try:
        # Find the most significant clinical indicators
        high_risk_features = {}

        # Check vital sign abnormalities
        if clinical_features.get('cardiac_risk_score', 0) >= 3.0:
            high_risk_features['Cardiac risk'] = clinical_features['cardiac_risk_score']
        if clinical_features.get('respiratory_distress_score', 0) >= 2.0:
            high_risk_features['Respiratory distress'] = clinical_features['respiratory_distress_score']
        if clinical_features.get('hemodynamic_instability', 0) >= 2.0:
            high_risk_features['Hemodynamic instability'] = clinical_features['hemodynamic_instability']
        if clinical_features.get('sepsis_risk_score', 0) >= 2.0:
            high_risk_features['Sepsis risk'] = clinical_features['sepsis_risk_score']

        # Check specific vitals
        spo2 = form_data.get('spo2', 97)
        hr = form_data.get('heart_rate', 75)
        bp_sys = form_data.get('bp_systolic', 120)
        temp = form_data.get('temperature', 37.0)

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
        symptoms = form_data.get('symptoms', [])
        symptom_explanations = []

        if 'altered_consciousness' in symptoms:
            symptom_explanations.append("altered consciousness")
        if 'severe_bleeding' in symptoms:
            symptom_explanations.append("severe bleeding")
        if 'seizure' in symptoms:
            symptom_explanations.append("seizure activity")
        if 'chest_pain' in symptoms and 'breathlessness' in symptoms:
            symptom_explanations.append("chest pain with difficulty breathing")
        elif 'chest_pain' in symptoms:
            symptom_explanations.append("chest pain")
        elif 'breathlessness' in symptoms:
            symptom_explanations.append("difficulty breathing")

        # Build explanation
        explanation_parts = []

        if vital_explanations:
            explanation_parts.append("vital signs showed " + ", ".join(vital_explanations[:2]))

        if symptom_explanations:
            explanation_parts.append("patient presented with " + ", ".join(symptom_explanations[:2]))

        if high_risk_features:
            top_risk = max(high_risk_features.items(), key=lambda x: x[1])
            explanation_parts.append(f"{top_risk[0].lower()} was significantly elevated")

        if explanation_parts:
            base_explanation = "Primary risk factors: " + "; ".join(explanation_parts[:3])
        else:
            base_explanation = "Multiple clinical indicators contributed to this triage decision"

        return f"{base_explanation}. Classified as {triage_level}."

    except Exception as e:
        print(f"[WARN] Risk explanation generation failed: {e}")
        return f"Advanced clinical analysis classified this case as {triage_level}."


def _get_legacy_risk_driver(features: np.ndarray, triage_level: str) -> str:
    """
    Legacy SHAP-based risk driver explanation
    """
    try:
        class_idx = {v: k for k, v in _label_map.items()}[triage_level]
        shap_vals = _explainer.shap_values(features.reshape(1, -1))
        class_shap = np.abs(shap_vals[0, :, class_idx])
        top_idx = int(np.argmax(class_shap))
        top_feat = _feature_names[top_idx]
        top_val = features[top_idx]

        # Format value with appropriate unit
        units = {
            "spo2": "%", "heart_rate": " bpm", "temperature": "°C",
            "bp_systolic": " mmHg", "bp_diastolic": " mmHg", "age": " yrs"
        }
        unit = units.get(top_feat, "")
        val_str = f"{top_val:.1f}{unit}" if top_val != -1 else "not recorded"

        return f"{top_feat.replace('_', ' ').title()} ({val_str}) was the primary driver of {triage_level} classification."

    except Exception as e:
        print(f"[WARN] SHAP risk driver failed: {e} - using fallback")
        return f"Triage level {triage_level} assigned by ML classifier."


def _safe_vital(val):
    """Return the value if valid, -1 if missing or sentinel."""
    if val is None or val == -1:
        return -1
    return val


def get_classifier_info() -> Dict[str, Any]:
    """Get information about the currently loaded classifier"""
    return {
        "classifier_type": _classifier_type,
        "model_info": _model_info,
        "is_enhanced": _classifier_type == "enhanced"
    }


# Backwards-compatible alias - main.py imports run_triage
run_triage = predict_triage