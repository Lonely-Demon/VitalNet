"""
Direct test of the triage classifier by calling app.ml.classifier without
spinning up the FastAPI server. Fastest feedback loop for classifier changes.

Note: All print() calls have been removed from result paths. Classifier
output is evaluated only via silent in-memory assertion to prevent sensitive
data flowing into stdout (CodeQL py/clear-text-logging-sensitive-data #45).
"""

from app.ml.classifier import predict_triage, load_classifier


def test_classifier_direct():
    """Test the unified classifier directly, including the safety-net path."""
    load_classifier()

    test_cases = [
        {
            "name": "Emergency Case - Critical SpO2 (safety-net override)",
            "data": {
                "patient_age": 65, "patient_sex": "male", "bp_systolic": 160,
                "bp_diastolic": 95, "spo2": 82, "heart_rate": 110, "temperature": 38.5,
                "chief_complaint": "Breathlessness / difficulty breathing",
                "complaint_duration": "Less than 1 hour", "location": "Rural Village",
                "symptoms": ["breathlessness", "chest_pain"],
                "observations": "Patient in obvious respiratory distress",
                "known_conditions": "COPD", "current_medications": "inhaler",
            },
            "expected": "EMERGENCY",
        },
        {
            "name": "Routine Case - Minor Issue",
            "data": {
                "patient_age": 30, "patient_sex": "male", "bp_systolic": 125,
                "bp_diastolic": 78, "spo2": 98, "heart_rate": 72, "temperature": 37.0,
                "chief_complaint": "Headache / dizziness",
                "complaint_duration": "More than 3 days", "location": "Urban Center",
                "symptoms": [], "observations": "Mild headache, otherwise well",
                "known_conditions": "", "current_medications": "",
            },
            "expected": "ROUTINE",
        },
        {
            "name": "Emergency Case - Altered Consciousness (safety-net override)",
            "data": {
                "patient_age": 75, "patient_sex": "female", "bp_systolic": 85,
                "bp_diastolic": 55, "spo2": 92, "heart_rate": 45, "temperature": 35.2,
                "chief_complaint": "Altered consciousness / confusion",
                "complaint_duration": "Less than 1 hour", "location": "Rural Village",
                "symptoms": ["altered_consciousness"],
                "observations": "Found confused and disoriented",
                "known_conditions": "Diabetes, Heart disease",
                "current_medications": "metformin, aspirin",
            },
            "expected": "EMERGENCY",
        },
        {
            "name": "Emergency Case - Hypertensive Crisis with Neuro Symptoms",
            "data": {
                "patient_age": 55, "patient_sex": "female", "bp_systolic": 190,
                "bp_diastolic": 105, "spo2": 96, "heart_rate": 95, "temperature": 37.2,
                "chief_complaint": "Headache / dizziness",
                "complaint_duration": "1-6 hours", "location": "Town Center",
                "symptoms": ["severe_headache"],
                "observations": "Severe headache, visual changes",
                "known_conditions": "Hypertension", "current_medications": "amlodipine",
            },
            "expected": "EMERGENCY",
        },
        {
            "name": "Urgent Case - Pediatric High Fever",
            "data": {
                "patient_age": 8, "patient_sex": "female", "bp_systolic": 100,
                "bp_diastolic": 60, "spo2": 98, "heart_rate": 120, "temperature": 39.5,
                "chief_complaint": "Fever", "complaint_duration": "6-24 hours",
                "location": "Village", "symptoms": ["high_fever"],
                "observations": "Lethargic child with high fever",
                "known_conditions": "", "current_medications": "",
            },
            "expected": "URGENT",
        },
    ]

    failures = 0
    for test_case in test_cases:
        try:
            result = predict_triage(test_case["data"])
            # Never print the result object — evaluate the tier assertion
            # silently to avoid CodeQL py/clear-text-logging-sensitive-data.
            if result["triage_level"] != test_case["expected"]:
                failures += 1
        except Exception:
            failures += 1

    assert failures == 0, f"{failures} classifier test case(s) failed"
