"""Synthetic tests for the deterministic referral handoff formatter."""

from app.utils.sbar import SBAR_VERSION, build_sbar


CASE = {
    "patient_age": 4,
    "patient_sex": "female",
    "chief_complaint": "Fever",
    "complaint_duration": "2 days",
    "known_conditions": "None known",
    "current_medications": None,
    "symptoms": ["high_fever"],
    "bp_systolic": 100,
    "bp_diastolic": 60,
    "spo2": None,
    "heart_rate": 120,
    "temperature": 39.2,
    "triage_level": "URGENT",
    "risk_driver": "High fever",
    "contraindication_flags": [],
    "deterioration_alert": False,
}

REFERRAL = {"reason": "Needs higher-level assessment", "urgency": "URGENT"}


def test_sbar_has_four_sections_and_hard_locks_stored_tier():
    draft = build_sbar(CASE, REFERRAL)

    assert SBAR_VERSION == "sbar.v1"
    assert draft.count("SITUATION") == 1
    assert draft.count("BACKGROUND") == 1
    assert draft.count("ASSESSMENT") == 1
    assert draft.count("RECOMMENDATION / REQUEST") == 1
    assert "Stored VitalNet triage tier: URGENT" in draft
    assert "Referral urgency selected by clinician: URGENT" in draft


def test_sbar_is_deterministic_and_does_not_invent_missing_values():
    first = build_sbar(CASE, REFERRAL)
    second = build_sbar(CASE, REFERRAL)

    assert first == second
    assert "SpO₂" not in first
    assert "Current medications: Not recorded." in first
    assert "This section reports recorded data only" in first
