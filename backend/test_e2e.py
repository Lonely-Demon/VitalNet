import requests
import json
import time
from config import settings
from supabase import create_client

BASE_URL = "http://localhost:8000"

def run_tests():
    print("--- Starting E2E Verification ---")
    
    print("\n1. Testing Health check...")
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"Health ({r.status_code}): {r.json()}")
    assert r.status_code == 200, "Health check failed"

    print("\n2. Testing unauthed endpoints (expecting 401)...")
    test_case = {
        "patient_name": "Test Patient Unauthed",
        "patient_age": 45,
        "patient_sex": "male",
        "location": "Test Village",
        "chief_complaint": "Chest pain / tightness",
        "complaint_duration": "1-6 hours",
        "symptoms": ["chest_pain"]
    }
    r1 = requests.post(f"{BASE_URL}/api/submit", json=test_case)
    print(f"Unauthed Submit: {r1.status_code}")
    assert r1.status_code == 401, f"Expected 401 for unauthed submit, got {r1.status_code}"
    
    r2 = requests.get(f"{BASE_URL}/api/cases")
    print(f"Unauthed Cases: {r2.status_code}")
    assert r2.status_code == 401, f"Expected 401 for unauthed cases, got {r2.status_code}"

    print("\n3. Authenticating Test Users via Supabase...")
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    
    try:
        asha_res = supabase.auth.sign_in_with_password({
            "email": "asha@test.vitalnet", 
            "password": "TestASHA2026!"
        })
        asha_jwt = asha_res.session.access_token
        print("Logged in as ASHA")
    except Exception as e:
        print(f"Failed to log in as ASHA: {e}")
        return
        
    try:
        doc_res = supabase.auth.sign_in_with_password({
            "email": "doctor@test.vitalnet", 
            "password": "TestDoctor2026!"
        })
        doc_jwt = doc_res.session.access_token
        print("Logged in as Doctor")
    except Exception as e:
        print(f"Failed to log in as Doctor: {e}")
        return

    print("\n4. Testing ASHA Case Submission...")
    test_case = {
        "client_id": "7829ca47-1941-4c74-a035-188e9cfec120",
        "patient_name": "Test Patient ASHA",
        "patient_age": 45,
        "patient_sex": "male",
        "location": "Test Village",
        "chief_complaint": "Chest pain / tightness",
        "complaint_duration": "1-6 hours",
        "symptoms": ["chest_pain"]
    }
    r_submit = requests.post(
        f"{BASE_URL}/api/submit",
        json=test_case,
        headers={"Authorization": f"Bearer {asha_jwt}"}
    )
    print(f"Submit Status: {r_submit.status_code}")
    if r_submit.status_code != 200:
        print("Submit Error:", r_submit.text)
    assert r_submit.status_code == 200, "ASHA submission failed"
    submitted_case = r_submit.json()
    case_id = submitted_case["id"]
    print(f"Case submitted successfully (ID: {case_id})")

    print("\n5. Testing ASHA getting cases (expecting 403)...")
    r_asha_cases = requests.get(
        f"{BASE_URL}/api/cases",
        headers={"Authorization": f"Bearer {asha_jwt}"}
    )
    print(f"ASHA Get Cases: {r_asha_cases.status_code}")
    assert r_asha_cases.status_code == 403, "ASHA should not access GET /cases"
    print("ASHA correctly denied access to global cases")

    print("\n6. Testing Doctor Access and Case Review...")
    r_doc_cases = requests.get(
        f"{BASE_URL}/api/cases",
        headers={"Authorization": f"Bearer {doc_jwt}"}
    )
    print(f"Doctor Get Cases: {r_doc_cases.status_code}")
    assert r_doc_cases.status_code == 200, "Doctor failed to get cases"
    response_data = r_doc_cases.json()
    cases = response_data.get("cases", [])
    print(f"Doctor retrieved {len(cases)} cases")
    
    # Check if our submitted case is in the list
    found = any(c["id"] == case_id for c in cases)
    assert found, "Submitted case not found in Doctor's queue"
    print("Submitted case verified in Doctor's queue")

    print("\n7. Testing Doctor Review Action...")
    r_review = requests.patch(
        f"{BASE_URL}/api/cases/{case_id}/review",
        headers={"Authorization": f"Bearer {doc_jwt}"}
    )
    print(f"Doctor Review Status: {r_review.status_code}")
    assert r_review.status_code == 200, "Doctor review failed"
    print("Doctor successfully marked case as reviewed")

    print("\n--- ALL TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    run_tests()
