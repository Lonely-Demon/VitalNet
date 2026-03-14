"""
Test script for the enhanced classifier
"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_enhanced_classifier():
    """Test the enhanced classifier with various scenarios"""

    print("[Enhanced Classifier Test] Starting comprehensive test...")

    # Test cases with different severity levels
    test_cases = [
        {
            "name": "Emergency Case - Severe Hypoxemia",
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
            },
            "expected": "EMERGENCY"
        },
        {
            "name": "Urgent Case - Hypertensive Crisis",
            "data": {
                "patient_age": 55,
                "patient_sex": "female",
                "bp_systolic": 190,  # Very high
                "bp_diastolic": 105,
                "spo2": 96,
                "heart_rate": 95,
                "temperature": 37.2,
                "chief_complaint": "Headache / dizziness",
                "complaint_duration": "1–6 hours",
                "location": "Town Center",
                "symptoms": ["severe_headache"],
                "observations": "Severe headache, visual changes",
                "known_conditions": "Hypertension",
                "current_medications": "amlodipine"
            },
            "expected": "EMERGENCY"
        },
        {
            "name": "Urgent Case - High Fever",
            "data": {
                "patient_age": 8,
                "patient_sex": "female",
                "bp_systolic": 100,
                "bp_diastolic": 60,
                "spo2": 98,
                "heart_rate": 120,
                "temperature": 39.5,  # High fever in child
                "chief_complaint": "Fever",
                "complaint_duration": "6–24 hours",
                "location": "Village",
                "symptoms": ["high_fever"],
                "observations": "Lethargic child with high fever",
                "known_conditions": "",
                "current_medications": ""
            },
            "expected": "URGENT"
        },
        {
            "name": "Routine Case - Minor Complaint",
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
            },
            "expected": "ROUTINE"
        },
        {
            "name": "Emergency Case - Altered Consciousness",
            "data": {
                "patient_age": 75,
                "patient_sex": "female",
                "bp_systolic": 90,  # Hypotensive
                "bp_diastolic": 55,
                "spo2": 93,
                "heart_rate": 45,   # Bradycardic
                "temperature": 35.5, # Hypothermic
                "chief_complaint": "Altered consciousness / confusion",
                "complaint_duration": "Less than 1 hour",
                "location": "Rural Village",
                "symptoms": ["altered_consciousness"],
                "observations": "Found confused and disoriented",
                "known_conditions": "Diabetes, Heart disease",
                "current_medications": "metformin, aspirin"
            },
            "expected": "EMERGENCY"
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] {test_case['name']}")
        print(f"Expected: {test_case['expected']}")

        try:
            # Submit the case
            response = requests.post(
                f"{API_BASE}/api/submit",
                json=test_case['data'],
                headers={
                    'Authorization': 'Bearer fake_token_for_testing',
                    'Content-Type': 'application/json'
                }
            )

            if response.status_code == 200:
                result = response.json()
                predicted_triage = result.get('triage_level', 'UNKNOWN')
                confidence = result.get('triage_confidence', 0)
                risk_driver = result.get('risk_driver', 'N/A')

                print(f"Predicted: {predicted_triage}")
                print(f"Confidence: {confidence:.3f}")
                print(f"Risk Driver: {risk_driver}")

                # Check if prediction matches expectation
                is_correct = predicted_triage == test_case['expected']
                print(f"Result: {'✅ CORRECT' if is_correct else '❌ INCORRECT'}")

                results.append({
                    'test_name': test_case['name'],
                    'expected': test_case['expected'],
                    'predicted': predicted_triage,
                    'confidence': confidence,
                    'correct': is_correct,
                    'risk_driver': risk_driver
                })

            else:
                print(f"❌ API Error: {response.status_code}")
                print(f"Response: {response.text}")

                results.append({
                    'test_name': test_case['name'],
                    'expected': test_case['expected'],
                    'predicted': 'ERROR',
                    'confidence': 0,
                    'correct': False,
                    'error': f"API Error {response.status_code}"
                })

        except Exception as e:
            print(f"❌ Test failed: {e}")
            results.append({
                'test_name': test_case['name'],
                'expected': test_case['expected'],
                'predicted': 'EXCEPTION',
                'confidence': 0,
                'correct': False,
                'error': str(e)
            })

    # Summary
    print(f"\n{'='*60}")
    print("ENHANCED CLASSIFIER TEST RESULTS")
    print(f"{'='*60}")

    correct_predictions = sum(1 for r in results if r['correct'])
    total_tests = len(results)
    accuracy = correct_predictions / total_tests if total_tests > 0 else 0

    print(f"Overall Accuracy: {correct_predictions}/{total_tests} ({accuracy:.1%})")
    print()

    for result in results:
        status = "✅" if result['correct'] else "❌"
        print(f"{status} {result['test_name']}")
        print(f"   Expected: {result['expected']}, Got: {result['predicted']}")
        if 'error' in result:
            print(f"   Error: {result['error']}")
        else:
            print(f"   Confidence: {result['confidence']:.3f}")
        print()

    # Test classifier info endpoint
    print("\n[Classifier Info Test]")
    try:
        health_response = requests.get(f"{API_BASE}/api/health")
        if health_response.status_code == 200:
            health_data = health_response.json()
            print("Health Check:")
            print(f"  Status: {health_data.get('status')}")
            print(f"  Database: {health_data.get('database')}")
            print(f"  Classifier: {health_data.get('classifier')}")

    except Exception as e:
        print(f"Health check failed: {e}")

    return results

if __name__ == "__main__":
    test_enhanced_classifier()