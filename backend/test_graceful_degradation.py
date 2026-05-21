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
    import app.ml.classifier as classifier
    from app.ml.classifier import load_classifier
    
    print("Testing classifier load with forced missing file to simulate failure...")
    
    # Save original PKL path and original classifier state
    orig_path = classifier.ENHANCED_PKL_PATH
    orig_type = classifier._classifier_type
    orig_classifier = classifier._classifier
    
    classifier.ENHANCED_PKL_PATH = Path("nonexistent_model_file.pkl")
    
    try:
        result = load_classifier()
        assert result is False, "load_classifier should return False when PKL file is missing"
        print("[PASS] Classifier load failed gracefully (returned False, no exception raised)")
    finally:
        # Restore PKL path and classifier state
        classifier.ENHANCED_PKL_PATH = orig_path
        classifier._classifier_type = orig_type
        classifier._classifier = orig_classifier
    
    return True


def test_fallback_prediction():
    """Test that predictions work even when ML model isn't loaded."""
    import app.ml.classifier as classifier
    from app.ml.classifier import predict_triage
    
    print("\nTesting fallback prediction system...")
    
    # Ensure classifier is in unloaded state for fallback test
    orig_type = classifier._classifier_type
    orig_classifier = classifier._classifier
    classifier._classifier_type = None
    classifier._classifier = None
    
    try:
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
        assert result["triage_level"].upper() == "EMERGENCY", "Should classify as EMERGENCY"
        assert result["model_version"] == "degraded-rules-v1.0", "Fallback model_version should be 'degraded-rules-v1.0'"
        assert "model_version" in result, "Should include model version"
        assert "85.0%" in result["risk_driver"], f"Risk driver should format spo2 float nicely, got: {result['risk_driver']}"
        assert "150.0 bpm" in result["risk_driver"], f"Risk driver should format heart rate float nicely, got: {result['risk_driver']}"
        print("[PASS] Emergency case handled correctly by fallback rules")
        
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
        assert result["triage_level"].upper() in ["ROUTINE", "NON-URGENT"], "Should classify as ROUTINE or NON-URGENT"
        assert result["model_version"] == "degraded-rules-v1.0", "Fallback model_version should be 'degraded-rules-v1.0'"
        print("[PASS] Non-urgent case handled correctly by fallback rules")
        
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
        assert result["triage_level"].upper() in ["URGENT", "EMERGENCY"], "Should classify as URGENT or EMERGENCY"
        assert result["model_version"] == "degraded-rules-v1.0", "Fallback model_version should be 'degraded-rules-v1.0'"
        print("[PASS] Urgent case handled correctly by fallback rules")
    finally:
        # Restore classifier state
        classifier._classifier_type = orig_type
        classifier._classifier = orig_classifier

    return True


def test_classifier_info():
    """Test that get_classifier_info() works even when model isn't loaded."""
    import app.ml.classifier as classifier
    from app.ml.classifier import get_classifier_info
    
    print("\nTesting classifier info retrieval...")
    
    # Save original state and clear to test info when model isn't loaded
    orig_type = classifier._classifier_type
    orig_classifier = classifier._classifier
    classifier._classifier_type = None
    classifier._classifier = None
    
    try:
        info = get_classifier_info()
        print(f"Classifier type (unloaded): {info['classifier_type']}")
        print(f"Is enhanced (unloaded): {info['is_enhanced']}")
        assert info["classifier_type"] is None
        assert info["is_enhanced"] is False
    finally:
        # Restore classifier state
        classifier._classifier_type = orig_type
        classifier._classifier = orig_classifier

    # Get info when loaded (if it was loaded)
    info = get_classifier_info()
    print(f"Classifier type (restored): {info['classifier_type']}")
    print(f"Is enhanced (restored): {info['is_enhanced']}")
    print("[PASS] Classifier info retrieved successfully")
    
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("VitalNet Graceful Degradation Test")
    print("Testing fix for R3-REL-RECOVER-R3-001")
    print("=" * 70)
    
    try:
        # 1. Load normally (if possible) to establish initial state
        from app.ml.classifier import load_classifier
        load_classifier()
        
        # 2. Run forced failure and fallback tests
        test_classifier_load_failure()
        test_fallback_prediction()
        test_classifier_info()
        
        print("\n" + "=" * 70)
        print("[PASS] ALL TESTS PASSED")
        print("The application can now start and function without the ML model.")
        print("=" * 70)
        sys.exit(0)
        
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
