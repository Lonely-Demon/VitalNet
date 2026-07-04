"""
Safety-property tests for the triage classifier. These assert the guarantees
that matter clinically, independent of the model's learned weights:

  1. Extreme single vitals ALWAYS escalate to EMERGENCY (deterministic safety
     net) — never depends on the ML model being right.
  2. Critical symptoms ALWAYS escalate to EMERGENCY.
  3. A concerning (NEWS2 score >= 2) single vital is NEVER left as ROUTINE.
  4. Healthy vitals with no symptoms classify as ROUTINE.
  5. Every non-safety-net result carries the low_confidence abstention flag.

No server or database needed. Run:
    cd backend && PYTHONPATH=. python tests/test_classifier_safety.py
    (or: pytest tests/test_classifier_safety.py -v)
"""
from app.ml.classifier import load_classifier, predict_triage, _news2_concerning_vital

load_classifier()

_BASE = {
    "patient_age": 40, "patient_sex": "male",
    "bp_systolic": 120, "bp_diastolic": 80, "spo2": 98, "heart_rate": 74,
    "temperature": 37.0, "symptoms": [], "chief_complaint": "Weakness / fatigue",
    "complaint_duration": "1-3 days", "location": "Rural District",
    "known_conditions": "", "current_medications": "",
}


def _case(**overrides):
    return {**_BASE, **overrides}


def test_extreme_vitals_always_emergency():
    extreme_cases = [
        {"spo2": 84}, {"spo2": 70},
        {"heart_rate": 34}, {"heart_rate": 180},
        {"bp_systolic": 65}, {"bp_systolic": 240},
        {"temperature": 42.0}, {"temperature": 32.5},
    ]
    for ov in extreme_cases:
        r = predict_triage(_case(**ov))
        assert r["triage_level"] == "EMERGENCY", f"{ov} -> {r['triage_level']} (expected EMERGENCY)"
        assert r["safety_net_triggered"] is True, f"{ov} should trigger the safety net"


def test_critical_symptoms_always_emergency():
    for sym in ["altered_consciousness", "seizure", "severe_bleeding", "swelling_face_throat"]:
        r = predict_triage(_case(symptoms=[sym]))
        assert r["triage_level"] == "EMERGENCY", f"symptom {sym} -> {r['triage_level']}"
        assert r["safety_net_triggered"] is True


def test_neonatal_fever_is_emergency():
    r = predict_triage(_case(patient_age=0.1, temperature=38.5))
    assert r["triage_level"] == "EMERGENCY"


def test_concerning_vital_never_routine():
    # NEWS2 score >= 2 band (concerning but not extreme) must never be ROUTINE.
    concerning_cases = [
        {"spo2": 92}, {"spo2": 91},
        {"heart_rate": 122}, {"heart_rate": 40},
        {"bp_systolic": 98}, {"bp_systolic": 185},
        {"temperature": 39.3}, {"temperature": 34.8},
    ]
    for ov in concerning_cases:
        # sanity: the predicate itself flags these
        assert _news2_concerning_vital(_case(**ov)) is not None, f"{ov} should be flagged concerning"
        r = predict_triage(_case(**ov))
        assert r["triage_level"] in ("URGENT", "EMERGENCY"), (
            f"{ov} -> {r['triage_level']} (concerning vital must never be ROUTINE)"
        )


def test_healthy_is_routine():
    r = predict_triage(_case())
    assert r["triage_level"] == "ROUTINE"
    assert r["low_confidence"] is False


def test_low_confidence_flag_present():
    r = predict_triage(_case())
    assert "low_confidence" in r and isinstance(r["low_confidence"], bool)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} safety tests passed")
    assert passed == len(fns), "safety tests failed"
