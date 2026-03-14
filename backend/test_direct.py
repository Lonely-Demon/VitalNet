"""
Simple test of the enhanced classifier by directly calling the classifier module
"""

import sys
import os

# Add the current directory to path
sys.path.append('/home/dharshan/VitalNet/backend')

from classifier import predict_triage, get_classifier_info, load_classifier

def test_enhanced_classifier_direct():
    """Test the enhanced classifier directly"""

    print("[Enhanced Classifier Direct Test] Starting test...")

    # Load the classifier first
    print("Loading classifier...")
    load_classifier()

    # Get classifier info
    try:
        info = get_classifier_info()
        print(f"\nClassifier Info:")
        print(f"  Type: {info['classifier_type']}")
        print(f"  Enhanced: {info['is_enhanced']}")
        print(f"  Model Info: {info['model_info']}")
    except Exception as e:
        print(f"Could not get classifier info: {e}")

    # Test cases
    test_cases = [
        {
            "name": "Emergency Case - Critical SpO2",
            "data": {
                "patient_age": 65,
                "patient_sex": "male",
                "bp_systolic": 160,
                "bp_diastolic": 95,
                "spo2": 85,  # Critical
                "heart_rate": 110,
                "temperature": 38.5,
                "chief_complaint": "Breathlessness / difficulty breathing",
                "complaint_duration": "Less than 1 hour",
                "location": "Rural Village",
                "symptoms": ["breathlessness", "chest_pain"],
                "observations": "Patient in obvious respiratory distress",
                "known_conditions": "COPD",
                "current_medications": "inhaler"
            }
        },
        {
            "name": "Routine Case - Minor Issue",
            "data": {
                "patient_age": 30,
                "patient_sex": "male",
                "bp_systolic": 125,
                "bp_diastolic": 78,
                "spo2": 98,
                "heart_rate": 72,
                "temperature": 37.0,
                "chief_complaint": "Headache / dizziness",
                "complaint_duration": "More than 3 days",
                "location": "Urban Center",
                "symptoms": [],
                "observations": "Mild headache, otherwise well",
                "known_conditions": "",
                "current_medications": ""
            }
        },
        {
            "name": "Emergency Case - Altered Consciousness",
            "data": {
                "patient_age": 75,
                "patient_sex": "female",
                "bp_systolic": 85,
                "bp_diastolic": 55,
                "spo2": 92,
                "heart_rate": 45,
                "temperature": 35.2,
                "chief_complaint": "Altered consciousness / confusion",
                "complaint_duration": "Less than 1 hour",
                "location": "Rural Village",
                "symptoms": ["altered_consciousness"],
                "observations": "Found confused and disoriented",
                "known_conditions": "Diabetes, Heart disease",
                "current_medications": "metformin, aspirin"
            }
        }
    ]

    print(f"\n{'='*60}")
    print("RUNNING ENHANCED CLASSIFIER TESTS")
    print(f"{'='*60}")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] {test_case['name']}")
        print("-" * 40)

        try:
            result = predict_triage(test_case['data'])

            print(f"Triage Level: {result['triage_level']}")
            print(f"Confidence: {result['confidence_score']:.3f}")
            print(f"Risk Driver: {result['risk_driver']}")

            # Show enhanced features if available
            if 'model_version' in result:
                print(f"Model Version: {result['model_version']}")
            if 'processing_time' in result:
                print(f"Processing: {result['processing_time']}")
            if 'fast_path' in result:
                print(f"Fast Path: {result['fast_path']}")
            if 'uncertainty' in result:
                uncertainty = result['uncertainty']
                if isinstance(uncertainty, dict):
                    print(f"Uncertainty: {uncertainty}")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("ENHANCED CLASSIFIER TEST COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    test_enhanced_classifier_direct()