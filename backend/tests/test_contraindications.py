"""
Tests for app/ml/contraindications.py — the deterministic, free-text
keyword-matched contraindication/interaction flag checker. See that
module's docstring for scope (a small curated list, not a general
drug-interaction database).

Run: cd backend && pytest tests/test_contraindications.py -v
"""
from app.ml.contraindications import check_contraindications
from app.ml.classifier import load_classifier, predict_triage

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


def test_no_medications_means_no_flags():
    assert check_contraindications(_case()) == []


def test_medication_alone_without_matching_condition_or_symptom_is_not_flagged():
    # Ibuprofen with no renal disease mentioned — nothing to flag.
    assert check_contraindications(_case(current_medications="ibuprofen 400mg")) == []


def test_nsaid_with_renal_condition_flagged():
    flags = check_contraindications(_case(
        current_medications="ibuprofen", known_conditions="chronic kidney disease",
    ))
    assert len(flags) == 1
    assert "NSAID" in flags[0]


def test_ace_inhibitor_with_renal_condition_flagged():
    flags = check_contraindications(_case(
        current_medications="lisinopril 10mg", known_conditions="renal impairment",
    ))
    assert len(flags) == 1
    assert "ACE inhibitor" in flags[0]


def test_metformin_with_persistent_vomiting_flagged():
    flags = check_contraindications(_case(
        current_medications="metformin 500mg", symptoms=["persistent_vomiting"],
    ))
    assert len(flags) == 1
    assert "Metformin" in flags[0]


def test_metformin_without_vomiting_not_flagged():
    assert check_contraindications(_case(current_medications="metformin 500mg")) == []


def test_anticoagulant_with_severe_bleeding_flagged():
    flags = check_contraindications(_case(
        current_medications="warfarin", symptoms=["severe_bleeding"],
    ))
    assert len(flags) == 1
    assert "Anticoagulant" in flags[0]


def test_beta_blocker_with_bradycardia_flagged():
    flags = check_contraindications(_case(
        current_medications="atenolol 50mg", heart_rate=48,
    ))
    assert len(flags) == 1
    assert "Beta-blocker" in flags[0]


def test_beta_blocker_with_normal_heart_rate_not_flagged():
    assert check_contraindications(_case(current_medications="atenolol 50mg", heart_rate=74)) == []


def test_insulin_with_altered_consciousness_flagged():
    flags = check_contraindications(_case(
        current_medications="insulin glargine", symptoms=["altered_consciousness"],
    ))
    assert len(flags) == 1
    assert "hypoglycemia" in flags[0].lower()


def test_multiple_medications_can_fire_multiple_flags():
    flags = check_contraindications(_case(
        current_medications="ibuprofen, lisinopril",
        known_conditions="chronic kidney disease",
    ))
    assert len(flags) == 2


def test_case_insensitive_matching():
    flags = check_contraindications(_case(
        current_medications="IBUPROFEN", known_conditions="Chronic KIDNEY Disease",
    ))
    assert len(flags) == 1


def test_predict_triage_includes_contraindication_flags_on_safety_net_path():
    result = predict_triage(_case(
        symptoms=["altered_consciousness"],  # triggers the safety net -> EMERGENCY
        current_medications="ibuprofen", known_conditions="renal disease",
    ))
    assert result["safety_net_triggered"] is True
    assert result["triage_level"] == "EMERGENCY"
    assert "contraindication_flags" in result
    assert len(result["contraindication_flags"]) == 1


def test_predict_triage_includes_contraindication_flags_on_model_path():
    result = predict_triage(_case(
        current_medications="ibuprofen", known_conditions="renal disease",
    ))
    assert result["safety_net_triggered"] is False
    assert "contraindication_flags" in result
    assert len(result["contraindication_flags"]) == 1
