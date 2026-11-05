"""
Milestone M1 Adversarial Challenge: Backend Classifier & Schema Validation
"""
import pytest
from pydantic import ValidationError
from app.ml.classifier import resolve_effective_age, predict_triage, load_classifier
from app.models.schemas import TriageOverride

load_classifier()

_BASE = {
    "patient_age": 40,
    "patient_sex": "male",
    "bp_systolic": 120,
    "bp_diastolic": 80,
    "spo2": 98,
    "heart_rate": 74,
    "temperature": 37.0,
    "symptoms": [],
    "chief_complaint": "General checkup",
    "complaint_duration": "1-3 days",
    "location": "Primary Health Centre",
    "known_conditions": "",
    "current_medications": "",
}


def _case(**overrides):
    return {**_BASE, **overrides}


def test_resolve_effective_age_boundaries():
    assert resolve_effective_age(0, 0) == 0.0
    assert pytest.approx(resolve_effective_age(0, 1), 1e-5) == 1.0 / 12.0
    assert pytest.approx(resolve_effective_age(0, 2), 1e-5) == 2.0 / 12.0
    assert pytest.approx(resolve_effective_age(0, 3), 1e-5) == 0.25
    assert pytest.approx(resolve_effective_age(0, 4), 1e-5) == 4.0 / 12.0
    assert resolve_effective_age(1, 18) == 1.5
    assert resolve_effective_age(2, 24) == 2.0  # patient_age >= 2 uses patient_age
    assert resolve_effective_age(5, 60) == 5.0
    assert resolve_effective_age(40, None) == 40.0
    assert resolve_effective_age(None, 6) == 0.5
    assert resolve_effective_age(None, None) is None


def test_neonatal_fever_adversarial_matrix():
    # 2-month-old infant (0.166 yr < 0.25) with fever 38.0C -> MUST trigger EMERGENCY safety net
    c_2m = _case(patient_age=0, age_months=2, temperature=38.0)
    r_2m = predict_triage(c_2m)
    assert r_2m["triage_level"] == "EMERGENCY"
    assert r_2m["safety_net_triggered"] is True
    assert "Neonatal fever" in r_2m["risk_driver"]

    # 4-month-old infant (0.333 yr >= 0.25) with isolated fever 38.5C -> MUST NOT trigger neonatal fever safety net
    c_4m = _case(patient_age=0, age_months=4, temperature=38.5)
    r_4m = predict_triage(c_4m)
    # The risk_driver must not be Neonatal fever
    assert "Neonatal fever" not in r_4m["risk_driver"]

    # Newborn (age 0, 0 months) with fever 38.0C -> MUST trigger neonatal fever safety net
    c_newborn = _case(patient_age=0, age_months=0, temperature=38.0)
    r_newborn = predict_triage(c_newborn)
    assert r_newborn["triage_level"] == "EMERGENCY"
    assert r_newborn["safety_net_triggered"] is True
    assert "Neonatal fever" in r_newborn["risk_driver"]


def test_triage_override_whitespace_and_control_chars_rejection():
    # Valid reason
    valid = TriageOverride(overridden_triage="EMERGENCY", override_reason="Clinician observation of distress")
    assert valid.override_reason == "Clinician observation of distress"

    # Valid with control chars and surrounding whitespace
    sanitized = TriageOverride(overridden_triage="EMERGENCY", override_reason="  Clinical distress \x00\x01  ")
    assert sanitized.override_reason == "Clinical distress"

    # Invalid empty or whitespace-only strings MUST raise ValidationError
    invalid_cases = [
        "",
        " ",
        "    ",
        "\t",
        "\n",
        "\r\n",
        "\t \n  \r\n  ",
        "\x00\x01\x1f",
        "  \x00\x01\x1f  ",
    ]
    for inv in invalid_cases:
        with pytest.raises(ValidationError) as exc_info:
            TriageOverride(overridden_triage="EMERGENCY", override_reason=inv)
        err_str = str(exc_info.value)
        assert ("override_reason cannot be empty or whitespace-only" in err_str or
                "String should have at least 1 character" in err_str)
