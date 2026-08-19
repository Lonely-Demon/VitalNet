"""Synthetic tests for governance-gated paediatric capture."""

import pytest
from pydantic import ValidationError

from app.models.schemas import IntakeForm
from app.utils.paediatric import build_paediatric_advisory


def base_form(**overrides):
    values = {
        "patient_name": "Synthetic child",
        "patient_age": 1,
        "patient_sex": "female",
        "chief_complaint": "Child unwell",
        "complaint_duration": "1 day",
        "location": "Synthetic village",
        "consent_captured": True,
    }
    values.update(overrides)
    return values


def test_age_months_and_muac_are_bounded_and_additive():
    form = IntakeForm(**base_form(age_months=8, muac_mm=115))
    assert form.age_months == 8
    assert form.muac_mm == 115


def test_age_months_is_rejected_for_children_aged_two_or_more():
    with pytest.raises(ValidationError, match="age_months"):
        IntakeForm(**base_form(patient_age=2, age_months=1))


def test_muac_is_rejected_for_children_aged_five_or_more():
    with pytest.raises(ValidationError, match="muac_mm"):
        IntakeForm(**base_form(patient_age=5, muac_mm=110))


def test_advisory_is_default_off_and_never_becomes_a_triage_flag():
    advisory = build_paediatric_advisory(
        {"patient_age": 1, "age_months": 8, "muac_mm": 110},
        enabled=False,
    )
    assert advisory["status"] == "disabled_pending_governance"
    assert advisory["eligible_for_muac_screen"] is None
    assert "needs_review" not in advisory
    assert "triage_level" not in advisory


def test_enabled_advisory_is_research_only_and_explicit_about_interpretation():
    advisory = build_paediatric_advisory(
        {"patient_age": 1, "age_months": 8, "muac_mm": 110},
        enabled=True,
    )
    assert advisory["status"] == "research_only"
    assert advisory["eligible_for_muac_screen"] is True
    assert advisory["muac_screen_status"] == "below_reference_threshold_full_assessment_needed"
    assert advisory["clinical_interpretation_required"] is True
