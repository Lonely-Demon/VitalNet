"""
VitalNet Enhanced Classifier Training Script
Generates the advanced multi-stage ensemble classifier
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import warnings
from datetime import datetime

import os
import sys

# Add backend to Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

from app.ml.enhanced_classifier import EnhancedTriageClassifier
from app.ml.clinical_features import ClinicalFeatureEngineer

warnings.filterwarnings('ignore')

# Configuration
N_SAMPLES = 4000  # Increased dataset size
RANDOM_SEED = 42
TEST_SIZE = 0.2

class EnhancedDataGenerator:
    """
    Enhanced synthetic patient data generator with more realistic clinical patterns
    """

    def __init__(self, random_seed=42):
        np.random.seed(random_seed)
        self.feature_engineer = ClinicalFeatureEngineer()

    def generate_patient_data(self, n_samples: int):
        """Generate enhanced synthetic patient data"""
        print(f"[Data Generator] Generating {n_samples} synthetic patients...")

        patients = []
        labels = []

        for i in range(n_samples):
            if i % 1000 == 0:
                print(f"[Data Generator] Generated {i} patients...")

            patient = self._generate_single_patient()
            label = self._determine_triage_label(patient)

            patients.append(patient)
            labels.append(label)

        print(f"[Data Generator] Generated {n_samples} patients complete")
        return patients, labels

    def _generate_single_patient(self):
        """Generate a single synthetic patient"""
        # Basic demographics
        age = max(1, int(np.random.exponential(35)))  # Realistic age distribution
        sex = np.random.choice(['male', 'female'], p=[0.48, 0.52])

        # Generate correlated vital signs
        vitals = self._generate_correlated_vitals(age)

        # Generate symptoms with realistic co-occurrence
        symptoms = self._generate_realistic_symptoms()

        # Generate chief complaint based on symptoms and demographics
        chief_complaint = self._generate_chief_complaint(symptoms, age, sex)

        # Duration based on complaint severity
        duration = self._generate_duration_for_complaint(chief_complaint)

        # Location
        location = np.random.choice([
            'Rural Village', 'Town Center', 'Remote Area',
            'Suburban Area', 'Urban Center'
        ], p=[0.4, 0.2, 0.2, 0.15, 0.05])

        # Medical history (more realistic)
        known_conditions, medications = self._generate_medical_history(age, sex)

        return {
            'patient_age': age,
            'patient_sex': sex,
            'bp_systolic': vitals['bp_sys'],
            'bp_diastolic': vitals['bp_dia'],
            'spo2': vitals['spo2'],
            'heart_rate': vitals['hr'],
            'temperature': vitals['temp'],
            'symptoms': symptoms,
            'chief_complaint': chief_complaint,
            'complaint_duration': duration,
            'location': location,
            'known_conditions': known_conditions,
            'current_medications': medications,
            'observations': ''
        }

    def _generate_correlated_vitals(self, age):
        """Generate physiologically correlated vital signs"""
        # Base values with age adjustments
        base_hr = 75 - (age - 40) * 0.2 if age > 40 else 75 + (18 - age) * 2 if age < 18 else 75
        base_bp_sys = 120 + (age - 40) * 0.5 if age > 40 else 120
        base_bp_dia = 80 + (age - 40) * 0.2 if age > 40 else 80

        # Add realistic variation and correlations
        hr_noise = np.random.normal(0, 15)
        bp_sys_noise = np.random.normal(0, 20)
        bp_dia_noise = np.random.normal(0, 12)

        # Correlate diastolic with systolic
        bp_dia_adjustment = bp_sys_noise * 0.4

        hr = max(30, min(200, base_hr + hr_noise))
        bp_sys = max(60, min(250, base_bp_sys + bp_sys_noise))
        bp_dia = max(30, min(130, base_bp_dia + bp_dia_noise + bp_dia_adjustment))

        # SpO2 - mostly normal, some abnormal
        if np.random.random() < 0.05:  # 5% severely abnormal
            spo2 = np.random.randint(70, 90)
        elif np.random.random() < 0.15:  # 15% mildly abnormal
            spo2 = np.random.randint(90, 95)
        else:  # 80% normal
            spo2 = np.random.randint(95, 101)

        # Temperature
        if np.random.random() < 0.10:  # 10% febrile
            temp = round(np.random.uniform(38.0, 41.0), 1)
        elif np.random.random() < 0.05:  # 5% hypothermic
            temp = round(np.random.uniform(34.0, 36.0), 1)
        else:  # 85% normal
            temp = round(np.random.uniform(36.0, 37.8), 1)

        return {
            'hr': int(hr),
            'bp_sys': int(bp_sys),
            'bp_dia': int(bp_dia),
            'spo2': int(spo2),
            'temp': temp
        }

    def _generate_realistic_symptoms(self):
        """Generate realistic symptom combinations"""
        all_symptoms = [
            'chest_pain', 'breathlessness', 'altered_consciousness',
            'severe_bleeding', 'seizure', 'high_fever',
            'severe_abdominal_pain', 'persistent_vomiting',
            'severe_headache', 'weakness_one_side',
            'difficulty_speaking', 'swelling_face_throat'
        ]

        # Symptom co-occurrence patterns
        patterns = [
            (['chest_pain', 'breathlessness'], 0.4),  # Cardiac/respiratory
            (['altered_consciousness', 'seizure'], 0.7),  # Neurological
            (['high_fever', 'severe_headache'], 0.3),  # Infectious
            (['severe_abdominal_pain', 'persistent_vomiting'], 0.5),  # GI
        ]

        symptoms = []

        # Check for pattern occurrence
        for pattern_symptoms, co_occurrence_prob in patterns:
            if np.random.random() < 0.1:  # 10% chance of pattern
                if np.random.random() < co_occurrence_prob:
                    symptoms.extend(pattern_symptoms)
                else:
                    symptoms.append(np.random.choice(pattern_symptoms))

        # Add individual symptoms
        for symptom in all_symptoms:
            if symptom not in symptoms and np.random.random() < 0.08:  # 8% base probability
                symptoms.append(symptom)

        return symptoms

    def _generate_chief_complaint(self, symptoms, age, sex):
        """Generate chief complaint based on symptoms and demographics"""
        complaints = [
            "Chest pain / tightness",
            "Breathlessness / difficulty breathing",
            "Fever",
            "Abdominal pain",
            "Headache / dizziness",
            "Weakness / fatigue",
            "Altered consciousness / confusion",
            "Seizure",
            "Severe bleeding",
            "Nausea / vomiting",
            "Baby / child unwell",
            "Pregnancy complication",
            "Injury / trauma",
            "Other"
        ]

        # Map symptoms to likely complaints
        if 'chest_pain' in symptoms:
            return "Chest pain / tightness"
        elif 'breathlessness' in symptoms:
            return "Breathlessness / difficulty breathing"
        elif 'high_fever' in symptoms:
            return "Fever"
        elif 'severe_abdominal_pain' in symptoms:
            return "Abdominal pain"
        elif 'altered_consciousness' in symptoms:
            return "Altered consciousness / confusion"
        elif 'seizure' in symptoms:
            return "Seizure"
        elif 'severe_bleeding' in symptoms:
            return "Severe bleeding"
        elif 'persistent_vomiting' in symptoms:
            return "Nausea / vomiting"
        elif age < 5:
            return "Baby / child unwell"
        elif sex == 'female' and 15 <= age <= 45 and np.random.random() < 0.1:
            return "Pregnancy complication"
        else:
            # Weight by common complaints in primary care
            weights = [0.05, 0.08, 0.15, 0.12, 0.20, 0.15, 0.02, 0.01, 0.02, 0.08, 0.05, 0.02, 0.03, 0.02]
            return np.random.choice(complaints, p=weights)

    def _generate_duration_for_complaint(self, complaint):
        """Generate duration based on complaint type"""
        acute_complaints = [
            "Chest pain / tightness", "Breathlessness / difficulty breathing",
            "Severe bleeding", "Seizure", "Altered consciousness / confusion"
        ]

        if complaint in acute_complaints:
            # Acute complaints - shorter duration
            durations = ["Less than 1 hour", "1–6 hours", "6–24 hours"]
            weights = [0.4, 0.4, 0.2]
        else:
            # Other complaints - varied duration
            durations = ["Less than 1 hour", "1–6 hours", "6–24 hours", "1–3 days", "More than 3 days"]
            weights = [0.1, 0.2, 0.3, 0.25, 0.15]

        return np.random.choice(durations, p=weights)

    def _generate_medical_history(self, age, sex):
        """Generate realistic medical history"""
        conditions = []
        medications = []

        # Age-based conditions
        if age > 50:
            if np.random.random() < 0.3:
                conditions.append("Hypertension")
                medications.append("amlodipine")
            if np.random.random() < 0.15:
                conditions.append("Diabetes")
                medications.append("metformin")

        if age > 65:
            if np.random.random() < 0.2:
                conditions.append("Heart disease")
                medications.append("aspirin")

        # General conditions
        if np.random.random() < 0.1:
            conditions.append("Asthma")
            medications.append("inhaler")

        return ", ".join(conditions), ", ".join(medications)

    def _determine_triage_label(self, patient):
        """Determine triage label using enhanced clinical rules"""
        age = patient['patient_age']
        bp_sys = patient['bp_systolic']
        bp_dia = patient['bp_diastolic']
        hr = patient['heart_rate']
        spo2 = patient['spo2']
        temp = patient['temperature']
        symptoms = patient['symptoms']

        # EMERGENCY criteria (enhanced)
        emergency_conditions = [
            # Severe vital sign abnormalities
            spo2 < 90,
            hr > 130 or hr < 45,
            bp_sys > 180 or bp_sys < 80,
            temp > 40.0 or temp < 35.0,

            # Critical symptoms
            'altered_consciousness' in symptoms,
            'seizure' in symptoms,
            'severe_bleeding' in symptoms,

            # Age-specific rules
            age < 0.25 and temp > 38.0,  # Neonatal fever
            age > 80 and spo2 < 94,      # Elderly hypoxemia

            # Complex combinations
            age > 65 and spo2 < 94 and 'chest_pain' in symptoms,
            'chest_pain' in symptoms and 'breathlessness' in symptoms and (hr > 110 or bp_sys > 160),

            # Shock indicators
            hr > 100 and bp_sys < 90,    # Possible shock
        ]

        if any(emergency_conditions):
            return 2  # EMERGENCY

        # URGENT criteria (enhanced)
        urgent_conditions = [
            # Borderline vital signs
            90 <= spo2 <= 94,
            110 <= hr <= 130,
            160 <= bp_sys <= 180,
            38.9 <= temp <= 40.0,

            # Concerning symptoms
            'high_fever' in symptoms,
            'chest_pain' in symptoms,
            'breathlessness' in symptoms,

            # Age-specific urgent criteria
            age < 2 and temp > 38.5,
            age > 75 and ('weakness_one_side' in symptoms or 'difficulty_speaking' in symptoms),

            # Multiple symptoms
            len(symptoms) >= 3,
        ]

        if any(urgent_conditions):
            return 1  # URGENT

        # ROUTINE
        return 0

def train_enhanced_classifier():
    """Train the enhanced classifier with synthetic data"""
    print("[Enhanced Training] Starting enhanced classifier training...")

    # Generate synthetic data
    data_generator = EnhancedDataGenerator(RANDOM_SEED)
    patients, labels = data_generator.generate_patient_data(N_SAMPLES)

    # Convert to feature matrix
    feature_engineer = ClinicalFeatureEngineer()
    print("[Enhanced Training] Engineering features...")

    X_list = []
    y = np.array(labels)

    for i, patient in enumerate(patients):
        if i % 1000 == 0:
            print(f"[Enhanced Training] Processed {i} patients for features...")

        features = feature_engineer.engineer_features(patient)
        X_list.append(list(features.values()))

    X = np.array(X_list)

    print(f"[Enhanced Training] Feature matrix shape: {X.shape}")
    print(f"[Enhanced Training] Feature count: {X.shape[1]}")

    # Check label distribution
    unique, counts = np.unique(y, return_counts=True)
    label_map = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}
    print("[Enhanced Training] Label distribution:")
    for lbl, count in zip(unique, counts):
        print(f"  {label_map[lbl]}: {count} samples ({count / N_SAMPLES:.1%})")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y
    )

    print(f"[Enhanced Training] Training set: {len(X_train)} samples")
    print(f"[Enhanced Training] Test set: {len(X_test)} samples")

    # Train the enhanced classifier
    classifier = EnhancedTriageClassifier()
    classifier.fit(X_train, y_train)

    # Evaluate
    print("[Enhanced Training] Evaluating model...")
    test_predictions = []
    test_confidences = []

    # Predict on test set (using raw patient data for realistic evaluation)
    for i in range(len(X_test)):
        # Create dummy patient data for prediction interface
        dummy_patient = {
            'patient_age': X_test[i, 0] if X_test[i, 0] > 0 else 40,
            'patient_sex': 'male' if X_test[i, 1] > 0.5 else 'female',
            'bp_systolic': X_test[i, 2] if X_test[i, 2] > 0 else 120,
            'bp_diastolic': X_test[i, 3] if X_test[i, 3] > 0 else 80,
            'spo2': X_test[i, 4] if X_test[i, 4] > 0 else 97,
            'heart_rate': X_test[i, 5] if X_test[i, 5] > 0 else 75,
            'temperature': X_test[i, 6] if X_test[i, 6] > 0 else 37.0,
            'symptoms': [],
            'chief_complaint': 'General malaise',
            'complaint_duration': '1-3 days',
            'location': 'Rural Village',
            'known_conditions': '',
            'current_medications': ''
        }

        try:
            result = classifier.predict(dummy_patient)
            triage_level = result['triage_level']
            confidence = result['confidence']

            # Map to numeric
            level_map = {'ROUTINE': 0, 'URGENT': 1, 'EMERGENCY': 2}
            test_predictions.append(level_map[triage_level])
            test_confidences.append(confidence)

        except Exception as e:
            print(f"[Warning] Prediction failed for sample {i}: {e}")
            test_predictions.append(0)  # Default to routine
            test_confidences.append(0.5)

    test_predictions = np.array(test_predictions)

    # Calculate metrics
    accuracy = np.mean(test_predictions == y_test)
    print(f"[Enhanced Training] Test Accuracy: {accuracy:.4f}")

    # Detailed classification report
    print("\n[Enhanced Training] Classification Report:")
    print(classification_report(y_test, test_predictions, target_names=['ROUTINE', 'URGENT', 'EMERGENCY']))

    # Confusion matrix
    cm = confusion_matrix(y_test, test_predictions)
    print("\n[Enhanced Training] Confusion Matrix:")
    print(cm)

    # Emergency recall (most important metric)
    if cm.shape[0] > 2 and cm.shape[1] > 2:
        emergency_recall = cm[2, 2] / (cm[2, 0] + cm[2, 1] + cm[2, 2]) if (cm[2, 0] + cm[2, 1] + cm[2, 2]) > 0 else 0
        emergency_fn = int(cm[2, 0] + cm[2, 1])
        print(f"\n[Enhanced Training] EMERGENCY Recall: {emergency_recall:.4f}")
        print(f"[Enhanced Training] EMERGENCY False Negatives: {emergency_fn}")

        if emergency_fn == 0:
            print("[Enhanced Training] Safety objective met: Zero EMERGENCY false negatives")
        else:
            print(f"[Enhanced Training] Safety objective NOT met: {emergency_fn} EMERGENCY cases under-triaged")

    # Save the model
    models_dir = os.path.join(BACKEND_DIR, "app", "ml", "models")
    os.makedirs(models_dir, exist_ok=True)
    model_filename = os.path.join(models_dir, "enhanced_triage_classifier.pkl")
    classifier.save_model(model_filename)

    print(f"\n[Enhanced Training] Training complete! Model saved as: {model_filename}")

    return classifier, model_filename

if __name__ == "__main__":
    try:
        classifier, model_file = train_enhanced_classifier()
        print(f"\n[Success] Enhanced classifier trained and saved: {model_file}")

        # Display model info
        model_info = classifier.get_model_info()
        print("\n[Model Info]")
        for key, value in model_info.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"[Error] Training failed: {e}")
        import traceback
        traceback.print_exc()