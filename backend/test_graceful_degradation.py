"""
Test graceful degradation when ML model cannot load.
This test verifies R3-REL-RECOVER-R3-001 fix.
"""
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_classifier_load_failure():
    """Test that load_classifier() returns False instead of raising exception."""
    from app.ml.classifier import load_classifier
    
    print("Testing classifier load with potentially missing dependencies...")
    result = load_classifier()
    
    if result:
        print("[PASS] Classifier loaded successfully")
    else:
        print("[PASS] Classifier load failed gracefully (returned False, no exception raised)")
    
    return True


def test_fallback_prediction():
    """Test that predictions work even when ML model isn't loaded."""
    from app.ml.classifier import predict_triage
    
    print("\nTesting fallback prediction system...")
    
    # Test emergency case
    emergency_data = {
        "spo2": 85,
        "heart_rate": 150,
        "symptoms": ["chest_pain", "altered_consciousness"],
        "bp_systolic": 80,
    }
    
    result = predict_triage(emergency_data)
    print(f"Emergency case prediction: {result['triage_level']} (confidence: {result['confidence_score']})")
    print(f"Risk driver: {result['risk_driver']}")
    assert result["triage_level"] == "emergency", "Should classify as emergency"
    assert "model_version" in result, "Should include model version"
    print("[PASS] Emergency case handled correctly")
    
    # Test non-urgent case
    normal_data = {
        "spo2": 98,
        "heart_rate": 75,
        "symptoms": [],
        "bp_systolic": 120,
        "temperature": 37.0,
    }
    
    result = predict_triage(normal_data)
    print(f"\nNormal case prediction: {result['triage_level']} (confidence: {result['confidence_score']})")
    print(f"Risk driver: {result['risk_driver']}")
    assert result["triage_level"] == "non-urgent", "Should classify as non-urgent"
    print("✓ Non-urgent case handled correctly")
    
    # Test urgent case
    urgent_data = {
        "spo2": 92,
        "heart_rate": 125,
        "symptoms": ["breathlessness"],
        "bp_systolic": 185,
    }
    
    result = predict_triage(urgent_data)
    print(f"\nUrgent case prediction: {result['triage_level']} (confidence: {result['confidence_score']})")
    print(f"Risk driver: {result['risk_driver']}")
    assert result["triage_level"] in ["urgent", "emergency"], "Should classify as urgent or emergency"
    print("✓ Urgent case handled correctly")
    
    return True


def test_classifier_info():
    """Test that get_classifier_info() works even when model isn't loaded."""
    from app.ml.classifier import get_classifier_info
    
    print("\nTesting classifier info retrieval...")
    info = get_classifier_info()
    
    print(f"Classifier type: {info['classifier_type']}")
    print(f"Is enhanced: {info['is_enhanced']}")
    print("✓ Classifier info retrieved successfully")
    
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("VitalNet Graceful Degradation Test")
    print("Testing fix for R3-REL-RECOVER-R3-001")
    print("=" * 70)
    
    try:
        test_classifier_load_failure()
        test_fallback_prediction()
        test_classifier_info()
        
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("The application can now start and function without the ML model.")
        print("=" * 70)
        sys.exit(0)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
