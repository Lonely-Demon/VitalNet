"""
Synthetic Unit Tests for ASHA Input Contract Remediation & Field Sensitivity Study.

Validates:
1. Frozen labels are computed once and reused across all arms.
2. All arms differ only in declared fields (invariants preserved).
3. observations removal does not change the current triage tier.
4. current_medications effects are reported through contraindication/review outputs
   rather than incorrectly attributed to the core model.
5. no_structured_symptoms, no_complaint_context, and nhamcs_like_partial_input arms are distinct.
6. Each missing-vital arm uses the five canonical model vitals.
7. Missing-vital reason is diagnostic metadata only and never interpreted as normal value.
8. Output passes recursive zero-leakage assertions.
9. No real-data adapter, NHAMCS file, Iran file, or production report is opened.
10. Field-utilization matrix is internally consistent with current code paths.
"""

import copy
import json
import os
import sys
from typing import Any, Dict, List
import pytest
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIXTURES_DIR = os.path.join(HERE, "fixtures")

if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from audit_asha_input_contract import (
    FIVE_VITAL_FIELDS,
    FIELD_UTILIZATION_MATRIX,
    CANDIDATE_FUTURE_FIELDS_RESEARCH_TABLE,
    generate_synthetic_asha_cohort,
    arm_current_full_form,
    arm_current_triage_contract,
    arm_no_observations,
    arm_no_medications,
    arm_no_structured_symptoms,
    arm_no_complaint_context,
    arm_nhamcs_like_partial_input,
    arm_missing_vital,
    evaluate_study_arm,
    run_asha_input_contract_study,
    assert_zero_patient_leakage,
)
import train_classifier as tc


@pytest.fixture
def synthetic_cohort() -> List[Dict[str, Any]]:
    """Generates a small deterministic synthetic cohort for test verification."""
    return generate_synthetic_asha_cohort(n=40, seed=42)


# ── Test 1: Label Freezing & Reuse ───────────────────────────────────────────

def test_frozen_labels_computed_once_and_reused(synthetic_cohort):
    """Labels must be computed once on full representation and reused across arms."""
    labels = [int(l) for l in tc.assign_triage_labels(synthetic_cohort)]
    assert len(labels) == len(synthetic_cohort)
    assert all(l in (0, 1, 2) for l in labels)

    # Evaluate multiple arms with the same labels
    full_arm = [arm_current_full_form(p) for p in synthetic_cohort]
    no_sym_arm = [arm_no_structured_symptoms(p) for p in synthetic_cohort]

    rep_full, preds_full, _ = evaluate_study_arm("current_full_form", full_arm, labels)
    rep_no_sym, preds_no_sym, _ = evaluate_study_arm(
        "no_structured_symptoms", no_sym_arm, labels, full_form_preds=preds_full
    )

    assert rep_full["cohort_size"] == len(synthetic_cohort)
    assert rep_no_sym["cohort_size"] == len(synthetic_cohort)
    # Frozen label distributions must match identically
    assert rep_full["frozen_label_distribution"] == rep_no_sym["frozen_label_distribution"]


# ── Test 2: Arms Differ Only in Declared Fields ──────────────────────────────

def test_all_arms_differ_only_in_declared_fields(synthetic_cohort):
    """Verifies that each arm mutates ONLY its declared fields."""
    for orig in synthetic_cohort:
        # 1. current_triage_contract
        tc_p = arm_current_triage_contract(orig)
        assert tc_p["patient_age"] == orig["patient_age"]
        assert tc_p["patient_sex"] == orig["patient_sex"]
        assert tc_p["temperature"] == orig["temperature"]
        assert tc_p["symptoms"] == orig["symptoms"]

        # 2. no_observations
        no_obs = arm_no_observations(orig)
        assert no_obs["observations"] == ""
        assert no_obs["patient_name"] == orig["patient_name"]
        assert no_obs["symptoms"] == orig["symptoms"]
        assert no_obs["temperature"] == orig["temperature"]

        # 3. no_medications
        no_med = arm_no_medications(orig)
        assert no_med["current_medications"] == ""
        assert no_med["known_conditions"] == orig["known_conditions"]
        assert no_med["symptoms"] == orig["symptoms"]

        # 4. no_structured_symptoms
        no_sym = arm_no_structured_symptoms(orig)
        assert no_sym["symptoms"] == []
        assert no_sym["chief_complaint"] == orig["chief_complaint"]
        assert no_sym["location"] == orig["location"]

        # 5. no_complaint_context
        no_ctx = arm_no_complaint_context(orig)
        assert no_ctx["chief_complaint"] == ""
        assert no_ctx["complaint_duration"] == ""
        assert no_ctx["location"] == ""
        assert no_ctx["known_conditions"] == ""
        assert no_ctx["symptoms"] == orig["symptoms"]

        # 6. nhamcs_like_partial_input
        nh_part = arm_nhamcs_like_partial_input(orig)
        assert nh_part["symptoms"] == []
        assert nh_part["chief_complaint"] == ""
        assert nh_part["location"] == ""
        assert "respiratory_rate" not in nh_part
        for vf in FIVE_VITAL_FIELDS:
            assert nh_part[vf] == orig[vf]


# ── Test 3: Observations Removal Does Not Change Triage Tier ────────────────

def test_observations_removal_does_not_change_triage_tier(synthetic_cohort):
    """Removing observations must produce zero triage tier changes."""
    labels = [int(l) for l in tc.assign_triage_labels(synthetic_cohort)]
    full_arm = [arm_current_full_form(p) for p in synthetic_cohort]
    no_obs_arm = [arm_no_observations(p) for p in synthetic_cohort]

    rep_full, preds_full, _ = evaluate_study_arm("current_full_form", full_arm, labels)
    rep_no_obs, preds_no_obs, _ = evaluate_study_arm(
        "no_observations", no_obs_arm, labels, full_form_preds=preds_full
    )

    assert preds_no_obs == preds_full, "Observations removal altered triage predictions!"
    disagree = rep_no_obs["disagreements_vs_current_full_form"]
    assert disagree["tier_disagreement_count"] == 0
    assert disagree["tier_disagreement_rate"] == 0.0


# ── Test 4: Current Medications Affects Contraindications, Not Core Model ───

def test_medications_affects_contraindications_separately_from_tier(synthetic_cohort):
    """Removing current_medications alters contraindication flags without altering base model tree features."""
    labels = [int(l) for l in tc.assign_triage_labels(synthetic_cohort)]

    # Explicitly ensure cohort has medication + condition pairs that trigger contraindications
    test_cohort = copy.deepcopy(synthetic_cohort)
    test_cohort[0]["current_medications"] = "ibuprofen 400mg"
    test_cohort[0]["known_conditions"] = "chronic kidney disease"
    test_cohort[1]["current_medications"] = "metformin 500mg"
    test_cohort[1]["symptoms"] = ["persistent_vomiting"]

    full_arm = [arm_current_full_form(p) for p in test_cohort]
    no_med_arm = [arm_no_medications(p) for p in test_cohort]

    rep_full, preds_full, contra_full = evaluate_study_arm("current_full_form", full_arm, labels)
    rep_no_med, preds_no_med, contra_no_med = evaluate_study_arm(
        "no_medications", no_med_arm, labels, full_form_preds=preds_full, full_form_contraindications=contra_full
    )

    # Core triage tier predictions should remain identical (medications is not in HistGradientBoosting feature vector)
    assert preds_no_med == preds_full
    # But contraindication flags should drop
    assert rep_full["contraindication_flag_count"] > 0
    assert rep_no_med["contraindication_flag_count"] == 0
    assert rep_no_med["disagreements_vs_current_full_form"]["contraindication_disagreement_count"] > 0


# ── Test 5: Distinctness of Ablation Arms ────────────────────────────────────

def test_symptoms_context_and_nhamcs_arms_are_distinct(synthetic_cohort):
    """Asserts that no_structured_symptoms, no_complaint_context, and nhamcs_like_partial_input are distinct."""
    p = synthetic_cohort[0]
    p_sym = arm_no_structured_symptoms(p)
    p_ctx = arm_no_complaint_context(p)
    p_nh = arm_nhamcs_like_partial_input(p)

    # p_sym has complaint and conditions, but empty symptoms
    assert p_sym["symptoms"] == []
    assert p_sym["chief_complaint"] != ""

    # p_ctx has symptoms, but empty complaint and conditions
    assert p_ctx["symptoms"] == p["symptoms"]
    assert p_ctx["chief_complaint"] == ""

    # p_nh has empty symptoms AND empty complaint
    assert p_nh["symptoms"] == []
    assert p_nh["chief_complaint"] == ""


# ── Test 6: Missing-Vital Arms Use 5 Canonical Vitals ────────────────────────

def test_missing_vital_arms_use_canonical_five_vitals(synthetic_cohort):
    """Verifies that missing vital arms correctly mask the five canonical vitals."""
    p = synthetic_cohort[0]

    for vf in FIVE_VITAL_FIELDS:
        arm_p = arm_missing_vital(p, (vf,))
        assert arm_p[vf] is None
        # All other vitals intact
        for other in FIVE_VITAL_FIELDS:
            if other != vf:
                assert arm_p[other] == p[other]


# ── Test 7: Missing-Vital Reason is Diagnostic Metadata Only ─────────────────

def test_missing_vital_never_treated_as_normal_value_by_harness(synthetic_cohort):
    """The study harness passes None for missing vitals, ensuring no fake 0 or normal replacement before feature engineering."""
    p = synthetic_cohort[0]
    arm_p = arm_missing_vital(p, ("temperature", "spo2"))

    assert arm_p["temperature"] is None
    assert arm_p["spo2"] is None
    # Feature engineer should handle None and calculate fallbacks internally
    fe_res = tc.engineer_features_batch([arm_p])[0]
    assert fe_res["temperature"] in (-1, -1.0)
    assert fe_res["spo2"] in (-1, -1.0)


# ── Test 8: Recursive Zero Patient Leakage Assertion ─────────────────────────

def test_output_passes_recursive_zero_leakage_assertion():
    """Validates that full study output passes zero-leakage recursion."""
    report = run_asha_input_contract_study(n=20, seed=999)
    assert_zero_patient_leakage(report)

    # Adversarial leakage test
    bad_rep = copy.deepcopy(report)
    bad_rep["study_arms"]["current_full_form"]["leaked_row"] = {"patient_name": "Ramesh"}
    with pytest.raises(AssertionError, match="Patient-level key 'patient_name'"):
        assert_zero_patient_leakage(bad_rep)


# ── Test 9: No Real-Data Adapters or Files Opened ─────────────────────────────

def test_no_real_data_adapters_opened(monkeypatch):
    """Monkeypatches real data sources to ensure synthetic study never touches them."""
    import evaluation_sources.nhamcs_2022 as nh_mod
    import evaluation_sources.iran_ed as iran_mod

    def _forbidden_call(*args, **kwargs):
        raise RuntimeError("CRITICAL VIOLATION: Real-data source was invoked during synthetic study!")

    monkeypatch.setattr(nh_mod.NHAMCS2022Source, "load_for_evaluation", _forbidden_call)
    monkeypatch.setattr(nh_mod.NHAMCS2022Source, "inspect", _forbidden_call)
    monkeypatch.setattr(iran_mod.IranEDSource, "load_for_evaluation", _forbidden_call)
    monkeypatch.setattr(iran_mod.IranEDSource, "inspect", _forbidden_call)

    # Run study
    report = run_asha_input_contract_study(n=25, seed=123)
    assert report["execution_mode"] == "synthetic_contract_study"


# ── Test 10: Field-Utilization Matrix Internal Consistency ───────────────────

def test_field_utilization_matrix_internal_consistency():
    """Verifies that every entry in FIELD_UTILIZATION_MATRIX adheres to expected schema and roles."""
    expected_attributes = [
        "captured_by_ui",
        "serialized_to_payload",
        "validated_by_schema",
        "passed_to_legacy_triage",
        "passed_to_offline_hybrid_triage",
        "used_by_core_feature_map",
        "used_by_safety_rules",
        "used_by_contraindication_review",
        "used_by_briefing_or_persistence_only",
        "clinical_operational_role",
    ]

    for field_name, meta in FIELD_UTILIZATION_MATRIX.items():
        for attr in expected_attributes:
            assert attr in meta, f"Field '{field_name}' missing attribute '{attr}'"

    # Specific architectural checks
    assert FIELD_UTILIZATION_MATRIX["observations"]["used_by_core_feature_map"] is False
    assert FIELD_UTILIZATION_MATRIX["observations"]["used_by_briefing_or_persistence_only"] is True

    assert FIELD_UTILIZATION_MATRIX["current_medications"]["used_by_core_feature_map"] is False
    assert FIELD_UTILIZATION_MATRIX["current_medications"]["used_by_contraindication_review"] is True

    assert FIELD_UTILIZATION_MATRIX["is_pregnant"]["used_by_safety_rules"] is True

    assert FIELD_UTILIZATION_MATRIX["respiratory_rate"]["captured_by_ui"] is False
    assert FIELD_UTILIZATION_MATRIX["respiratory_rate"]["passed_to_legacy_triage"] is False

    assert FIELD_UTILIZATION_MATRIX["consent_captured"]["used_by_briefing_or_persistence_only"] is True
    assert FIELD_UTILIZATION_MATRIX["patient_key"]["used_by_briefing_or_persistence_only"] is True
    assert FIELD_UTILIZATION_MATRIX["human_review_requested"]["used_by_briefing_or_persistence_only"] is True

    # Check candidate future fields table
    assert len(CANDIDATE_FUTURE_FIELDS_RESEARCH_TABLE) >= 8
    for item in CANDIDATE_FUTURE_FIELDS_RESEARCH_TABLE:
        assert "field_name" in item
        assert "clinical_rationale" in item
        assert "collection_feasibility_in_phc" in item
        assert "contract_and_clinical_review_status" in item
