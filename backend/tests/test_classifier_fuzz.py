"""
Property / fuzz robustness tests for predict_triage.

The two-layer architecture (deterministic safety net + trained model) makes
implicit promises the golden/safety tests don't exercise directly:
  1. predict_triage NEVER crashes and NEVER emits a malformed result on ANY
     input the Pydantic schema can produce — including every combination of
     present/absent optional vitals, boundary ages, and large symptom sets.
  2. The output contract always holds: triage_level is one of the three tiers,
     confidence is a real number in [0, 1], the flags are booleans, and no
     field is NaN/inf.
  3. The safety-net invariant holds under randomized fuzzing, not just the
     hand-picked cases in test_classifier_safety.py: an extreme single vital
     or a critical symptom ALWAYS yields EMERGENCY, for any surrounding noise.

This is the runnable check for "the classifier is robust", distinct from
"the classifier is accurate". Deterministic (seeded) so a failure reproduces.

Run:
    cd backend && PYTHONPATH=. python tests/test_classifier_fuzz.py
    (or: pytest tests/test_classifier_fuzz.py -q)
"""
import math
import random

from app.ml.classifier import load_classifier, predict_triage
from app.models.schemas import ALLOWED_SYMPTOMS

load_classifier()

TIERS = {"ROUTINE", "URGENT", "EMERGENCY"}
SYMPTOMS = sorted(ALLOWED_SYMPTOMS)
SEX = ["male", "female", "other"]
COMPLAINTS = ["Fever", "Chest pain / tightness", "Weakness / fatigue", "Other", ""]
DURATIONS = ["Less than 1 hour", "1–6 hours", "6–24 hours", "1–3 days", "More than 3 days", ""]

# Schema-reachable value pools, including None (optional vitals often absent in
# the field) and the exact inclusive bounds from schemas.py.
AGES = [0, 0.08, 0.25, 0.5, 1, 2, 5, 12, 17, 18, 40, 65, 90, 120]
BP_SYS = [None, 30, 60, 70, 90, 100, 120, 160, 180, 220, 300]
BP_DIA = [None, 30, 50, 70, 80, 110, 120, 200]
SPO2 = [None, 50, 70, 84, 85, 88, 91, 92, 95, 100]
HR = [None, 10, 34, 35, 40, 74, 120, 130, 170, 171, 250]
TEMP = [None, 25.0, 32.5, 33.0, 35.0, 37.0, 38.0, 39.1, 41.5, 45.0]


def _random_case(rng):
    n_sym = rng.randint(0, min(len(SYMPTOMS), 6))
    return {
        "patient_age": rng.choice(AGES),
        "patient_sex": rng.choice(SEX),
        "bp_systolic": rng.choice(BP_SYS),
        "bp_diastolic": rng.choice(BP_DIA),
        "spo2": rng.choice(SPO2),
        "heart_rate": rng.choice(HR),
        "temperature": rng.choice(TEMP),
        "symptoms": rng.sample(SYMPTOMS, n_sym),
        "chief_complaint": rng.choice(COMPLAINTS),
        "complaint_duration": rng.choice(DURATIONS),
        "location": rng.choice(["Rural District", "Mumbai City", "", "Remote Tribal Area"]),
        "known_conditions": rng.choice(["", "diabetes", "hypertension, heart disease"]),
        "current_medications": rng.choice(["", "metformin", "warfarin, atenolol"]),
        "observations": "",
        "is_pregnant": rng.choice([None, False, True]),
    }


def _assert_valid_result(r, case):
    assert isinstance(r, dict), f"non-dict result for {case}"
    assert r["triage_level"] in TIERS, f"bad tier {r['triage_level']} for {case}"
    c = r["confidence_score"]
    assert isinstance(c, (int, float)) and not math.isnan(c) and not math.isinf(c), f"bad confidence {c}"
    assert 0.0 <= c <= 1.0, f"confidence out of range {c} for {case}"
    assert isinstance(r["safety_net_triggered"], bool)
    assert isinstance(r["low_confidence"], bool)
    assert isinstance(r.get("contraindication_flags", []), list)


def test_fuzz_never_crashes_and_output_contract_holds():
    rng = random.Random(20260710)
    for _ in range(6000):
        case = _random_case(rng)
        r = predict_triage(case)          # must not raise
        _assert_valid_result(r, case)


def test_fuzz_extreme_vital_is_always_emergency():
    """An extreme single vital (safety-net territory) must force EMERGENCY no
    matter what other (schema-valid) noise surrounds it."""
    rng = random.Random(11)
    extreme = [
        {"spo2": 84}, {"spo2": 60},
        {"heart_rate": 34}, {"heart_rate": 200},
        {"bp_systolic": 60}, {"bp_systolic": 240, "bp_diastolic": 120},
        {"temperature": 42.0}, {"temperature": 32.0},
    ]
    for _ in range(2000):
        case = _random_case(rng)
        ov = rng.choice(extreme)
        # Don't let a random low systolic invalidate the diastolic>=systolic rule
        case = {**case, **ov}
        if "bp_systolic" in ov and case.get("bp_diastolic") is not None:
            if case["bp_diastolic"] >= case["bp_systolic"]:
                case["bp_diastolic"] = None
        r = predict_triage(case)
        assert r["triage_level"] == "EMERGENCY", f"extreme {ov} not EMERGENCY: {case} -> {r['triage_level']}"
        assert r["safety_net_triggered"] is True


def test_fuzz_critical_symptom_is_always_emergency():
    """A critical symptom must force EMERGENCY regardless of vitals noise."""
    rng = random.Random(22)
    critical = ["altered_consciousness", "seizure", "severe_bleeding", "swelling_face_throat"]
    for _ in range(2000):
        case = _random_case(rng)
        case["symptoms"] = list({*case["symptoms"], rng.choice(critical)})
        r = predict_triage(case)
        assert r["triage_level"] == "EMERGENCY", f"critical symptom case not EMERGENCY: {case['symptoms']}"
        assert r["safety_net_triggered"] is True


def test_fuzz_all_vitals_missing_still_classifies():
    """The rural no-equipment reality: every optional vital absent. Must still
    return a valid tier (symptoms/complaint drive it), never crash."""
    rng = random.Random(33)
    for _ in range(1000):
        case = _random_case(rng)
        for k in ("bp_systolic", "bp_diastolic", "spo2", "heart_rate", "temperature"):
            case[k] = None
        r = predict_triage(case)
        _assert_valid_result(r, case)


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
    print(f"\n{passed}/{len(fns)} fuzz tests passed")
    assert passed == len(fns), "fuzz tests failed"
