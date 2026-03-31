"""
VitalNet Enhanced Multi-Stage Ensemble Classifier
Advanced clinical triage classifier with specialized models and uncertainty quantification
"""

import numpy as np
import pickle
import warnings
from typing import Dict, List, Any, Optional, Tuple, cast
from datetime import datetime
from copy import deepcopy
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    VotingClassifier,
    RandomForestClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.calibration import CalibratedClassifierCV
import joblib  # noqa: F401 — kept for unpickling legacy model files via pickle protocol

from app.ml.clinical_features import ClinicalFeatureEngineer
from app.ml.model_contract import (
    CONFIDENCE_FLOOR,
    FEATURE_SCHEMA_VERSION,
    LIVE_DRIFT_WINDOW,
    MODEL_VERSION,
    UNCERTAINTY_FLOOR,
)

warnings.filterwarnings('ignore')


class EnhancedTriageClassifier:
    """
    Multi-stage ensemble classifier for clinical triage

    Stages:
    1. Emergency Detector - Ultra-fast emergency detection
    2. Symptom Classifier - Symptom pattern recognition
    3. Clinical Reasoning - Advanced feature analysis
    4. Meta-learner - Final ensemble decision
    """

    def __init__(self):
        self.feature_engineer = ClinicalFeatureEngineer()
        self.emergency_threshold = 0.85
        self.is_trained = False

        # Model components
        self.emergency_detector = None
        self.symptom_classifier = None
        self.clinical_reasoner = None
        self.meta_classifier = None
        self.probability_calibrator = None

        # Feature information
        self.feature_names = []
        self.feature_count = 0

        # Model metadata
        self.model_version = MODEL_VERSION
        self.feature_schema_version = FEATURE_SCHEMA_VERSION
        self.training_date = None
        self.performance_metrics = {}

    def _create_models(self):
        """Initialize the ensemble models"""

        # Stage 1: Emergency Detector (Fast, High Recall)
        self.emergency_detector = HistGradientBoostingClassifier(
            max_iter=100,
            max_depth=4,
            learning_rate=0.15,
            random_state=42,
            class_weight={0: 1.0, 1: 3.0, 2: 15.0}  # Heavy emergency weighting
        )

        # Stage 2: Symptom Classifier (Pattern Recognition)
        self.symptom_classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight={0: 1.0, 1: 2.5, 2: 12.0}
        )

        # Stage 3: Clinical Reasoner (Deep Analysis)
        self.clinical_reasoner = HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=8,
            learning_rate=0.1,
            random_state=42,
            class_weight={0: 1.0, 1: 2.0, 2: 10.0}
        )

        # Stage 4: Meta-learner (Final Decision)
        self.meta_classifier = VotingClassifier(
            estimators=[
                ('emergency', self.emergency_detector),
                ('symptoms', self.symptom_classifier),
                ('clinical', self.clinical_reasoner)
            ],
            voting='soft'  # Use probability averages
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'EnhancedTriageClassifier':
        """
        Train the ensemble classifier

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,)

        Returns:
            Self for method chaining
        """
        print(f"[Enhanced Classifier] Training with {len(X)} samples, {X.shape[1]} features")

        # Create models
        self._create_models()

        # Train individual models
        print("[Enhanced Classifier] Training emergency detector...")
        self.emergency_detector = cast(HistGradientBoostingClassifier, self.emergency_detector)
        self.emergency_detector.fit(X, y)

        print("[Enhanced Classifier] Training symptom classifier...")
        self.symptom_classifier = cast(RandomForestClassifier, self.symptom_classifier)
        self.symptom_classifier.fit(X, y)

        print("[Enhanced Classifier] Training clinical reasoner...")
        self.clinical_reasoner = cast(HistGradientBoostingClassifier, self.clinical_reasoner)
        self.clinical_reasoner.fit(X, y)

        print("[Enhanced Classifier] Training meta-classifier...")
        self.meta_classifier = cast(VotingClassifier, self.meta_classifier)
        self.meta_classifier.fit(X, y)

        # Calibrate probabilities for better uncertainty quantification
        print("[Enhanced Classifier] Calibrating probabilities...")
        self.probability_calibrator = CalibratedClassifierCV(
            self.meta_classifier, method='isotonic', cv=3
        )
        self.probability_calibrator.fit(X, y)

        # Store training metadata
        self.is_trained = True
        self.training_date = datetime.now()
        self.feature_count = X.shape[1]

        # Calculate performance metrics
        self._calculate_performance_metrics(X, y)

        print(f"[Enhanced Classifier] Training complete. Accuracy: {self.performance_metrics['accuracy']:.4f}")

        return self

    def predict(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict triage level for a patient

        Args:
            patient_data: Raw patient data dictionary

        Returns:
            Dictionary containing prediction, confidence, and metadata
        """
        if not self.is_trained:
            raise ValueError("Classifier must be trained before prediction")

        # Engineer features
        features = self.feature_engineer.engineer_features(patient_data)
        red_flags = self.feature_engineer.detect_red_flags(patient_data)
        feature_vector = np.array(list(features.values()), dtype=float).reshape(1, -1)

        meta_classifier = cast(VotingClassifier, self.meta_classifier)
        emergency_detector = cast(HistGradientBoostingClassifier, self.emergency_detector)
        symptom_classifier = cast(RandomForestClassifier, self.symptom_classifier)
        clinical_reasoner = cast(HistGradientBoostingClassifier, self.clinical_reasoner)
        probability_calibrator = cast(CalibratedClassifierCV, self.probability_calibrator)

        if red_flags.get("must_escalate"):
            emergency_prob = np.array([0.0, 0.0, 1.0], dtype=float)
            uncertainty = self._calculate_uncertainty([emergency_prob])
            result = {
                'triage_level': 'EMERGENCY',
                'confidence': 1.0,
                'probabilities': {
                    'ROUTINE': 0.0,
                    'URGENT': 0.0,
                    'EMERGENCY': 1.0,
                },
                'uncertainty': uncertainty,
                'fast_path': True,
                'processing_time': 'ultra_fast',
                'model_version': self.model_version,
                'feature_schema_version': self.feature_schema_version,
                'needs_review': True,
                'review_reason': 'Explicit clinical red flag detected',
                'red_flags': red_flags,
                'individual_predictions': {
                    'emergency_detector': emergency_prob.tolist(),
                    'symptom_classifier': emergency_prob.tolist(),
                    'clinical_reasoner': emergency_prob.tolist(),
                },
                'clinical_features': features,
            }
            self._record_live_prediction(result)
            return result

        # Stage 1: Emergency fast-path
        emergency_prob = emergency_detector.predict_proba(feature_vector)[0]
        emergency_uncertainty = self._calculate_uncertainty([emergency_prob])
        if emergency_prob[2] > self.emergency_threshold:
            result = {
                'triage_level': 'EMERGENCY',
                'confidence': float(emergency_prob[2]),
                'fast_path': True,
                'processing_time': 'ultra_fast',
                'model_version': self.model_version,
                'feature_schema_version': self.feature_schema_version,
                'uncertainty': emergency_uncertainty,
                'needs_review': bool(emergency_uncertainty.get('high_uncertainty')),
                'review_reason': 'Emergency fast-path triggered',
                'red_flags': red_flags,
                'clinical_features': features
            }
            self._record_live_prediction(result)
            return result

        # Full ensemble prediction
        probabilities = probability_calibrator.predict_proba(feature_vector)[0]
        predicted_class = int(np.argmax(probabilities))

        # Get individual model predictions for uncertainty calculation
        individual_predictions = [
            emergency_detector.predict_proba(feature_vector)[0],
            symptom_classifier.predict_proba(feature_vector)[0],
            clinical_reasoner.predict_proba(feature_vector)[0]
        ]

        uncertainty = self._calculate_uncertainty(individual_predictions)
        needs_review = bool(
            uncertainty['high_uncertainty']
            or uncertainty['agreement_score'] < UNCERTAINTY_FLOOR
            or float(probabilities[predicted_class]) < CONFIDENCE_FLOOR
        )

        # Map class to label
        class_labels = {0: 'ROUTINE', 1: 'URGENT', 2: 'EMERGENCY'}
        triage_level = class_labels[predicted_class]

        result = {
            'triage_level': triage_level,
            'confidence': float(probabilities[predicted_class]),
            'probabilities': {
                'ROUTINE': float(probabilities[0]),
                'URGENT': float(probabilities[1]),
                'EMERGENCY': float(probabilities[2])
            },
            'uncertainty': uncertainty,
            'fast_path': False,
            'processing_time': 'full_analysis',
            'model_version': self.model_version,
            'feature_schema_version': self.feature_schema_version,
            'needs_review': needs_review,
            'review_reason': 'Low confidence or high uncertainty' if needs_review else None,
            'red_flags': red_flags,
            'individual_predictions': {
                'emergency_detector': individual_predictions[0].tolist(),
                'symptom_classifier': individual_predictions[1].tolist(),
                'clinical_reasoner': individual_predictions[2].tolist()
            },
            'clinical_features': features
        }

        self._record_live_prediction(result)
        return result

    def _calculate_uncertainty(self, predictions: List[np.ndarray]) -> Dict[str, float]:
        """
        Calculate prediction uncertainty metrics

        Args:
            predictions: List of probability arrays from different models

        Returns:
            Dictionary of uncertainty metrics
        """
        predictions_array = np.array(predictions)

        # Epistemic uncertainty (model disagreement)
        epistemic_uncertainty = np.var(predictions_array, axis=0)

        # Total uncertainty (entropy of mean prediction)
        mean_prediction = np.mean(predictions_array, axis=0)
        entropy = -np.sum(mean_prediction * np.log(mean_prediction + 1e-10))

        # Agreement score (how much models agree)
        max_class_variance = np.max(epistemic_uncertainty)
        agreement_score = 1.0 - (max_class_variance / 0.25)  # Normalize to 0-1

        return {
            'epistemic_uncertainty': float(np.max(epistemic_uncertainty)),
            'total_entropy': float(entropy),
            'agreement_score': float(max(0.0, agreement_score)),
            'high_uncertainty': bool(max_class_variance > 0.1 or entropy > 0.8)
        }

    def _record_live_prediction(self, result: Dict[str, Any]) -> None:
        """Update lightweight live drift metrics from recent predictions."""
        live_drift = self.performance_metrics.setdefault(
            'live_drift',
            {
                'window_size': LIVE_DRIFT_WINDOW,
                'recent_confidences': [],
                'recent_uncertainty': [],
                'review_count': 0,
            },
        )

        confidence = float(result.get('confidence', 0.0))
        uncertainty = result.get('uncertainty', {}) or {}

        live_drift['recent_confidences'].append(confidence)
        live_drift['recent_uncertainty'].append(float(uncertainty.get('epistemic_uncertainty', 0.0)))
        if result.get('needs_review'):
            live_drift['review_count'] += 1

        if len(live_drift['recent_confidences']) > LIVE_DRIFT_WINDOW:
            live_drift['recent_confidences'] = live_drift['recent_confidences'][-LIVE_DRIFT_WINDOW:]
            live_drift['recent_uncertainty'] = live_drift['recent_uncertainty'][-LIVE_DRIFT_WINDOW:]

        live_drift['average_confidence'] = float(np.mean(live_drift['recent_confidences'])) if live_drift['recent_confidences'] else 0.0
        live_drift['average_uncertainty'] = float(np.mean(live_drift['recent_uncertainty'])) if live_drift['recent_uncertainty'] else 0.0

    def _calculate_performance_metrics(self, X: np.ndarray, y: np.ndarray):
        """Calculate and store performance metrics"""
        try:
            # Cross-validation scores
            meta_classifier = cast(VotingClassifier, self.meta_classifier)
            cv_scores = cross_val_score(meta_classifier, X, y, cv=5)

            # Predictions for confusion matrix
            y_pred = meta_classifier.predict(X)

            # Emergency recall (most important metric)
            cm = confusion_matrix(y, y_pred)
            emergency_recall = cm[2, 2] / (cm[2, 0] + cm[2, 1] + cm[2, 2]) if cm.shape[0] > 2 else 0

            self.performance_metrics = {
                'accuracy': float(np.mean(cv_scores)),
                'accuracy_std': float(np.std(cv_scores)),
                'emergency_recall': float(emergency_recall),
                'training_accuracy': float(accuracy_score(y, y_pred)),
                'confusion_matrix': cm.tolist()
            }

        except Exception as e:
            print(f"[Warning] Could not calculate all performance metrics: {e}")
            self.performance_metrics = {
                'accuracy': 0.0,
                'emergency_recall': 0.0,
                'training_accuracy': 0.0
            }

    def save_model(self, filepath: str):
        """Save the trained model to disk"""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")

        model_data = {
            'emergency_detector': self.emergency_detector,
            'symptom_classifier': self.symptom_classifier,
            'clinical_reasoner': self.clinical_reasoner,
            'meta_classifier': self.meta_classifier,
            'probability_calibrator': self.probability_calibrator,
            'feature_engineer': self.feature_engineer,
            'feature_count': self.feature_count,
            'model_version': self.model_version,
            'feature_schema_version': self.feature_schema_version,
            'training_date': self.training_date,
            'performance_metrics': self.performance_metrics,
            'emergency_threshold': self.emergency_threshold
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f, protocol=5)

        print(f"[Enhanced Classifier] Model saved to {filepath}")

    @classmethod
    def load_model(cls, filepath: str) -> 'EnhancedTriageClassifier':
        """Load a trained model from disk"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        # Create new instance
        classifier = cls()

        # Load components
        classifier.emergency_detector = model_data['emergency_detector']
        classifier.symptom_classifier = model_data['symptom_classifier']
        classifier.clinical_reasoner = model_data['clinical_reasoner']
        classifier.meta_classifier = model_data['meta_classifier']
        classifier.probability_calibrator = model_data['probability_calibrator']
        classifier.feature_engineer = model_data['feature_engineer']
        classifier.feature_count = model_data['feature_count']
        classifier.model_version = model_data['model_version']
        classifier.feature_schema_version = model_data.get('feature_schema_version', FEATURE_SCHEMA_VERSION)
        classifier.training_date = model_data['training_date']
        classifier.performance_metrics = model_data['performance_metrics']
        classifier.emergency_threshold = model_data.get('emergency_threshold', 0.85)
        classifier.is_trained = True

        print(f"[Enhanced Classifier] Model loaded from {filepath}")
        print(f"[Enhanced Classifier] Version: {classifier.model_version}")
        print(f"[Enhanced Classifier] Training date: {classifier.training_date}")
        print(f"[Enhanced Classifier] Accuracy: {classifier.performance_metrics.get('accuracy', 'N/A')}")

        return classifier

    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive model information"""
        return {
            'model_version': self.model_version,
            'feature_schema_version': self.feature_schema_version,
            'training_date': self.training_date.isoformat() if self.training_date else None,
            'is_trained': self.is_trained,
            'feature_count': self.feature_count,
            'performance_metrics': self.performance_metrics,
            'emergency_threshold': self.emergency_threshold,
            'model_components': {
                'emergency_detector': str(type(self.emergency_detector).__name__),
                'symptom_classifier': str(type(self.symptom_classifier).__name__),
                'clinical_reasoner': str(type(self.clinical_reasoner).__name__),
                'meta_classifier': str(type(self.meta_classifier).__name__)
            }
        }


# ContinualLearningManager removed — it was an inert stub.
# Will be reintroduced properly when the PATCH /api/cases/{id}/outcome endpoint
# and doctor feedback UI are scoped in a future sprint.
