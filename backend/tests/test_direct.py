"""
Direct test of the triage classifier by calling app.ml.classifier without
spinning up the FastAPI server. Fastest feedback loop for classifier changes.
"""

from app.ml.classifier import predict_triage, get_classifier_info, load_classifier


def test_classifier_direct():
    """Test the unified classifier directly, including the safety-net path."""

    print("[Classifier Direct Test] Starting test...")

    print("Loading classifier...")
    load_classifier()

    try:
        info = get_classifier_info()
        print("\nClassifier Info:")
        print(f"  Type: {info['classifier_type']}")
        print(f"  Model Info: {info['model_info']}")
    except Exception as e:
        print(f"Could not get classifier info: {e}")

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
                "complaint_duration": "1–6 hours", "location": "Town Center",
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
                "chief_complaint": "Fever", "complaint_duration": "6–24 hours",
                "location": "Village", "symptoms": ["high_fever"],
                "observations": "Lethargic child with high fever",
                "known_conditions": "", "current_medications": "",
            },
            "expected": "URGENT",
        },
    ]

    print(f"\n{'=' * 60}")
    print("RUNNING CLASSIFIER TESTS")
    print(f"{'=' * 60}")

    failures = 0
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] {test_case['name']}")
        print("-" * 40)

        try:
            result = predict_triage(test_case["data"])

            # Synthetic fixture data defined in this file, printed to stdout
            # for a human running this script locally; no real patient data
            # ever reaches this path. Suppression uses the current CodeQL
            # inline syntax (codeql[query-id]) — GitHub's default CodeQL
            # setup does not honor the legacy lgtm.com lgtm[query-id] syntax.
            print(f"Triage Level: {result['triage_level']}")
            print(f"Confidence: {result['confidence_score']:.3f}")
            print(f"Risk Driver: {result['risk_driver']}")
            print(f"Safety net triggered: {result.get('safety_net_triggered')}")  # codeql[py/clear-text-logging-sensitive-data]

            if result["triage_level"] != test_case["expected"]:
                print(f"FAILED: expected {test_case['expected']}, got {result['triage_level']}")  # codeql[py/clear-text-logging-sensitive-data]
                failures += 1
            else:
                print("PASSED")

        except Exception as e:
            print(f"Test raised an exception: {e}")
            import traceback
            traceback.print_exc()
            failures += 1

    print(f"\n{'=' * 60}")
    print(f"CLASSIFIER TEST COMPLETE — {len(test_cases) - failures}/{len(test_cases)} passed")
    print(f"{'=' * 60}")

    assert failures == 0, f"{failures} classifier test case(s) failed"


if __name__ == "__main__":
    test_classifier_direct()
