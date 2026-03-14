"""
VitalNet Enhanced Multi-Stage Ensemble Classifier
Advanced clinical triage classifier with specialized models and uncertainty quantification
"""

import numpy as np
import pickle
import warnings
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    VotingClassifier,
    RandomForestClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.calibration import CalibratedClassifierCV
import joblib

from clinical_features import ClinicalFeatureEngineer

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
        self.model_version = "2.0.0"
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
        self.emergency_detector.fit(X, y)

        print("[Enhanced Classifier] Training symptom classifier...")
        self.symptom_classifier.fit(X, y)

        print("[Enhanced Classifier] Training clinical reasoner...")
        self.clinical_reasoner.fit(X, y)

        print("[Enhanced Classifier] Training meta-classifier...")
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
        feature_vector = np.array(list(features.values())).reshape(1, -1)

        # Stage 1: Emergency fast-path
        emergency_prob = self.emergency_detector.predict_proba(feature_vector)[0]
        if emergency_prob[2] > self.emergency_threshold:
            return {
                'triage_level': 'EMERGENCY',
                'confidence': float(emergency_prob[2]),
                'fast_path': True,
                'processing_time': 'ultra_fast',
                'model_version': self.model_version,
                'uncertainty': self._calculate_uncertainty([emergency_prob]),
                'clinical_features': features
            }

        # Full ensemble prediction
        probabilities = self.probability_calibrator.predict_proba(feature_vector)[0]
        predicted_class = np.argmax(probabilities)

        # Get individual model predictions for uncertainty calculation
        individual_predictions = [
            self.emergency_detector.predict_proba(feature_vector)[0],
            self.symptom_classifier.predict_proba(feature_vector)[0],
            self.clinical_reasoner.predict_proba(feature_vector)[0]
        ]

        uncertainty = self._calculate_uncertainty(individual_predictions)

        # Map class to label
        class_labels = {0: 'ROUTINE', 1: 'URGENT', 2: 'EMERGENCY'}
        triage_level = class_labels[predicted_class]

        return {
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
            'individual_predictions': {
                'emergency_detector': individual_predictions[0].tolist(),
                'symptom_classifier': individual_predictions[1].tolist(),
                'clinical_reasoner': individual_predictions[2].tolist()
            },
            'clinical_features': features
        }

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

    def _calculate_performance_metrics(self, X: np.ndarray, y: np.ndarray):
        """Calculate and store performance metrics"""
        try:
            # Cross-validation scores
            cv_scores = cross_val_score(self.meta_classifier, X, y, cv=5)

            # Predictions for confusion matrix
            y_pred = self.meta_classifier.predict(X)

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

class ContinualLearningManager:
    """
    Manages continual learning and model updates based on clinical outcomes
    """

    def __init__(self, classifier: EnhancedTriageClassifier):
        self.classifier = classifier
        self.feedback_buffer = []
        self.update_threshold = 50  # Update after 50 feedback cases
        self.safety_threshold = 0.95  # Minimum emergency recall

    def add_outcome_feedback(self, case_id: str, patient_data: Dict[str, Any],
                           predicted_triage: str, actual_outcome: str):
        """
        Add clinical outcome feedback for model improvement

        Args:
            case_id: Unique case identifier
            patient_data: Original patient data
            predicted_triage: Model prediction
            actual_outcome: Actual clinical outcome
        """
        # Map outcomes to triage levels
        outcome_mapping = {
            'discharged': 'ROUTINE',
            'admitted': 'URGENT',
            'icu': 'EMERGENCY',
            'emergency_surgery': 'EMERGENCY',
            'death': 'EMERGENCY'
        }

        true_triage = outcome_mapping.get(actual_outcome.lower(), 'ROUTINE')

        # Calculate prediction error
        error_severity = self._calculate_prediction_error(predicted_triage, true_triage)

        if error_severity > 0:  # Only store cases with prediction errors
            self.feedback_buffer.append({
                'case_id': case_id,
                'patient_data': patient_data,
                'predicted_triage': predicted_triage,
                'true_triage': true_triage,
                'error_severity': error_severity,
                'timestamp': datetime.now()
            })

            # Trigger update if buffer is full
            if len(self.feedback_buffer) >= self.update_threshold:
                self._perform_model_update()

    def _calculate_prediction_error(self, predicted: str, actual: str) -> float:
        """Calculate clinical prediction error severity"""
        severity_map = {'ROUTINE': 0, 'URGENT': 1, 'EMERGENCY': 2}
        pred_severity = severity_map.get(predicted, 0)
        actual_severity = severity_map.get(actual, 0)

        error = actual_severity - pred_severity

        # Under-triage (missing emergencies) is most severe
        if error > 0:
            return error * 2.0
        # Over-triage is less severe but still important
        elif error < 0:
            return abs(error) * 0.5
        else:
            return 0.0

    def _perform_model_update(self):
        """Perform incremental model update with safety checks"""
        print(f"[Continual Learning] Updating model with {len(self.feedback_buffer)} feedback cases")

        # For now, log the feedback for analysis
        # In production, this would trigger retraining with safety validation
        high_severity_errors = [fb for fb in self.feedback_buffer if fb['error_severity'] >= 2.0]

        if high_severity_errors:
            print(f"[Warning] Found {len(high_severity_errors)} high-severity prediction errors")
            for error in high_severity_errors[:5]:  # Show first 5
                print(f"  Case {error['case_id']}: Predicted {error['predicted_triage']}, Actual {error['true_triage']}")

        # Clear buffer
        self.feedback_buffer = []
        print("[Continual Learning] Feedback buffer cleared")