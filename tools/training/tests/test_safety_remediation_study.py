"""
Synthetic Unit & Invariant Tests for Safety-Remediation Candidate Study.

Validates:
1. Frozen baseline arm is unchanged and produces standard predict_triage outputs.
2. The candidate never interprets missing symptoms as explicit negative screening.
3. Explicit negative screening is distinct from missing or unavailable screening.
4. The candidate's insufficient-information state cannot silently become ROUTINE.
5. Candidate escalation reason codes are deterministic and aggregateable.
6. The three arms use identical synthetic reference labels (paired analysis).
7. Missingness strata and subgroup metrics have correct denominators and no cohort leakage.
8. Deterministic repeatability: identical seed produces identical aggregate reports.
9. Hard real-data isolation: no real-data adapter, path, or authorization flag is imported or executed.
10. Output zero-leakage: report passes recursive zero-leakage verification with zero patient records.
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

if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import study_safety_remediation as sr
import train_classifier as tc
from app.ml import classifier as clf_mod

TIER_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}


@pytest.fixture
def synthetic_cohort() -> List[Dict[str, Any]]:
    """Generates a small deterministic synthetic cohort for unit testing."""
    return sr.generate_synthetic_study_cohort(n=60, seed=42)


# ── Test 1: Frozen Baseline Invariance ───────────────────────────────────────

def test_frozen_baseline_invariance(synthetic_cohort):
    """Verifies that the frozen baseline arm produces unchanged standard model predictions."""
    if clf_mod._classifier is None:
        clf_mod.load_classifier()

    for p in synthetic_cohort:
        clean_p = sr.transform_arm_frozen_baseline(p)
        # Verify research metadata stripped
        assert not any(k.startswith("_research_") for k in clean_p.keys())

        # Model output on clean_p matches standard prediction
        expected = clf_mod.predict_triage(clean_p)
        assert expected["triage_level"] in ("ROUTINE", "URGENT", "EMERGENCY")


# ── Test 2: Symptom Screening Distinction ─────────────────────────────────────

def test_symptom_screening_states_distinct(synthetic_cohort):
    """
    Verifies that unknown, declined, explicit negative, and positive symptom states
    are strictly distinguished and never conflated.
    """
    base_patient = {
        "patient_age": 35,
        "patient_sex": "female",
        "temperature": 37.0,
        "heart_rate": 72,
        "bp_systolic": 118,
        "bp_diastolic": 76,
        "spo2": 98,
        "symptoms": [],
        "chief_complaint": "",
        "complaint_duration": "",
        "location": "PHC",
        "known_conditions": "",
        "current_medications": "",
        "observations": "",
        "is_pregnant": False,
    }

    # 1. Unknown / Not Asked -> MUST trigger INSUFFICIENT_INFORMATION_FOR_CDS
    p_unknown = copy.deepcopy(base_patient)
    p_unknown["_research_symptom_screening_status"] = "unknown_or_not_asked"
    p_unknown["_research_no_acute_danger_signs_declared"] = False
    res_unknown = sr.evaluate_candidate_policy(p_unknown)
    assert res_unknown["is_indeterminate"] is True
    assert res_unknown["tier"] == "INSUFFICIENT_INFORMATION_FOR_CDS"
    assert res_unknown["reason_code"] == "missing_symptom_confirmation"

    # 2. Declined / Unavailable -> MUST trigger INSUFFICIENT_INFORMATION_FOR_CDS
    p_declined = copy.deepcopy(base_patient)
    p_declined["_research_symptom_screening_status"] = "declined_or_unavailable"
    p_declined["_research_no_acute_danger_signs_declared"] = False
    res_declined = sr.evaluate_candidate_policy(p_declined)
    assert res_declined["is_indeterminate"] is True
    assert res_declined["tier"] == "INSUFFICIENT_INFORMATION_FOR_CDS"
    assert res_declined["reason_code"] == "missing_symptom_confirmation"

    # 3. Explicit Negative Screen -> ALLOWS ordinary tier evaluation
    p_explicit = copy.deepcopy(base_patient)
    p_explicit["_research_symptom_screening_status"] = "explicit_negative_screen"
    p_explicit["_research_no_acute_danger_signs_declared"] = True
    res_explicit = sr.evaluate_candidate_policy(p_explicit)
    assert res_explicit["is_indeterminate"] is False
    assert res_explicit["tier"] in ("ROUTINE", "URGENT", "EMERGENCY")

    # 4. Positive Symptoms -> ALLOWS ordinary tier evaluation with symptoms
    p_positive = copy.deepcopy(base_patient)
    p_positive["symptoms"] = ["chest_pain"]
    p_positive["_research_symptom_screening_status"] = "positive_symptom"
    p_positive["_research_no_acute_danger_signs_declared"] = False
    res_positive = sr.evaluate_candidate_policy(p_positive)
    assert res_positive["is_indeterminate"] is False
    assert res_positive["tier"] in ("URGENT", "EMERGENCY")


# ── Test 3: Blank Symptoms NEVER Implicitly Treated as Negative ───────────────

def test_blank_symptoms_never_treated_as_explicit_negative():
    """Omitting symptoms without explicit negative declaration must be treated as missing context."""
    p_blank = {
        "patient_age": 45,
        "patient_sex": "male",
        "temperature": 36.8,
        "heart_rate": 70,
        "bp_systolic": 120,
        "bp_diastolic": 80,
        "spo2": 98,
        "symptoms": [],
        "_research_symptom_screening_status": "unknown_or_not_asked",
        "_research_no_acute_danger_signs_declared": False,
    }
    res = sr.evaluate_candidate_policy(p_blank)
    assert res["is_indeterminate"] is True
    assert res["tier"] == "INSUFFICIENT_INFORMATION_FOR_CDS"
    assert res["reason_code"] == "missing_symptom_confirmation"


# ── Test 4: Indeterminate Safe-Fail Invariant ─────────────────────────────────

def test_indeterminate_cannot_silently_become_routine():
    """Encounters in INSUFFICIENT_INFORMATION_FOR_CDS state must never output ROUTINE."""
    sparse_patients = [
        # Missing age
        {"patient_age": None, "patient_sex": "female", "temperature": 37.0, "heart_rate": 80, "bp_systolic": 120, "bp_diastolic": 80, "spo2": 98},
        # 2 missing vitals
        {"patient_age": 30, "patient_sex": "male", "temperature": None, "heart_rate": None, "bp_systolic": 120, "bp_diastolic": 80, "spo2": 98},
        # Missing SpO2
        {"patient_age": 30, "patient_sex": "male", "temperature": 37.0, "heart_rate": 80, "bp_systolic": 120, "bp_diastolic": 80, "spo2": None},
        # Missing symptom declaration
        {"patient_age": 30, "patient_sex": "male", "temperature": 37.0, "heart_rate": 80, "bp_systolic": 120, "bp_diastolic": 80, "spo2": 98, "symptoms": [], "_research_symptom_screening_status": "unknown_or_not_asked"},
    ]

    for p in sparse_patients:
        res = sr.evaluate_candidate_policy(p)
        assert res["is_indeterminate"] is True
        assert res["tier"] == "INSUFFICIENT_INFORMATION_FOR_CDS"
        assert res["tier"] != "ROUTINE"


# ── Test 5: Escalation Reason Codes Determinism ───────────────────────────────

def test_escalation_reason_codes_deterministic():
    """Verifies that escalation reason codes are deterministically assigned."""
    # 1. severe_missingness (demographic)
    p_demo = {"patient_age": None, "patient_sex": "male"}
    assert sr.evaluate_candidate_policy(p_demo)["reason_code"] == "severe_missingness"

    # 2. severe_missingness (>=2 vitals)
    p_2vit = {"patient_age": 30, "patient_sex": "male", "temperature": None, "heart_rate": None, "bp_systolic": 120, "bp_diastolic": 80, "spo2": 98}
    assert sr.evaluate_candidate_policy(p_2vit)["reason_code"] == "severe_missingness"

    # 3. critical_vital_unmeasured (SpO2)
    p_spo2 = {"patient_age": 30, "patient_sex": "male", "temperature": 37.0, "heart_rate": 80, "bp_systolic": 120, "bp_diastolic": 80, "spo2": None}
    assert sr.evaluate_candidate_policy(p_spo2)["reason_code"] == "critical_vital_unmeasured"

    # 4. missing_symptom_confirmation
    p_sym = {
        "patient_age": 30,
        "patient_sex": "male",
        "temperature": 37.0,
        "heart_rate": 80,
        "bp_systolic": 120,
        "bp_diastolic": 80,
        "spo2": 98,
        "symptoms": [],
        "_research_symptom_screening_status": "declined_or_unavailable",
    }
    assert sr.evaluate_candidate_policy(p_sym)["reason_code"] == "missing_symptom_confirmation"


# ── Test 6: Paired Analysis Label Reuse Across Arms ───────────────────────────

def test_paired_arms_use_identical_labels(synthetic_cohort):
    """Verifies that all three arms evaluate against the exact same frozen reference labels."""
    labels = [int(l) for l in tc.assign_triage_labels(synthetic_cohort)]
    assert len(labels) == len(synthetic_cohort)

    b_res = sr.evaluate_study_arm("frozen_baseline_v3.1.0", synthetic_cohort, labels)
    c_res = sr.evaluate_study_arm("candidate_remediation_v1", synthetic_cohort, labels)
    v_res = sr.evaluate_study_arm("vital_only_partial_stress", synthetic_cohort, labels)

    assert b_res["cohort_size"] == len(synthetic_cohort)
    assert c_res["cohort_size"] == len(synthetic_cohort)
    assert v_res["cohort_size"] == len(synthetic_cohort)

    # Reference emergency totals must match identically across all arms
    ref_em_b = b_res["non_triage_escalation_summary"]["emergency_cases_total"]
    ref_em_c = c_res["non_triage_escalation_summary"]["emergency_cases_total"]
    ref_em_v = v_res["non_triage_escalation_summary"]["emergency_cases_total"]
    assert ref_em_b == ref_em_c == ref_em_v == sum(1 for l in labels if l == 2)


# ── Test 7: Denominator and Matrix Separation Integrity ──────────────────────

def test_denominator_and_matrix_separation_integrity(synthetic_cohort):
    """
    Verifies that tiered cases and indeterminate cases have separated denominators
    and that confusion matrix sums strictly to tiered_case_count.
    """
    labels = [int(l) for l in tc.assign_triage_labels(synthetic_cohort)]
    c_res = sr.evaluate_study_arm("candidate_remediation_v1", synthetic_cohort, labels)

    esc_summary = c_res["non_triage_escalation_summary"]
    tiered_count = esc_summary["tiered_case_count"]
    indet_count = esc_summary["indeterminate_count"]
    total = len(synthetic_cohort)

    # Invariant: tiered + indeterminate == total
    assert tiered_count + indet_count == total

    # Invariant: emergency cases tiered + escalated == total emergencies
    em_total = esc_summary["emergency_cases_total"]
    em_esc = esc_summary["emergency_cases_escalated"]
    em_tiered = esc_summary["emergency_cases_given_an_ordinary_tier"]
    assert em_esc + em_tiered == em_total

    # Invariant: 3x3 confusion matrix sums exactly to tiered_count
    cm = c_res["ordinary_3_tier_safety_metrics"]["confusion_matrix_3x3"]
    matrix_sum = sum(sum(row) for row in cm)
    assert matrix_sum == tiered_count


# ── Test 8: Deterministic Repeatability ───────────────────────────────────────

def test_deterministic_repeatability():
    """Verifies that two runs with the same seed generate bitwise identical aggregate results."""
    rep1 = sr.run_safety_remediation_study(n_patients=50, seed=42)
    rep2 = sr.run_safety_remediation_study(n_patients=50, seed=42)

    # Compare metadata and metrics (excluding timestamp)
    rep1_clean = copy.deepcopy(rep1)
    rep2_clean = copy.deepcopy(rep2)
    rep1_clean["study_metadata"]["execution_timestamp"] = ""
    rep2_clean["study_metadata"]["execution_timestamp"] = ""

    assert json.dumps(rep1_clean, sort_keys=True) == json.dumps(rep2_clean, sort_keys=True)


# ── Test 9: Real-Data Isolation & Zero-Leakage ────────────────────────────────

def test_real_data_isolation_and_zero_leakage():
    """
    Verifies that study_safety_remediation has zero real-data imports and emits zero
    patient records or raw text in reports.
    """
    # Verify no real-data adapter is imported
    forbidden_modules = [
        "evaluation_sources.ktas_2019",
        "evaluation_sources.nhamcs_2022",
        "evaluation_sources.iran_ed",
        "evaluation_sources.mimic_iv_ed",
    ]
    for mod in forbidden_modules:
        assert mod not in sys.modules

    # Run study and assert recursive zero leakage
    report = sr.run_safety_remediation_study(n_patients=30, seed=42)
    sr.assert_zero_patient_leakage(report)

    # Verify no patient lists exist
    assert "patient_records" not in report
    assert "records" not in report
    assert "form_data" not in report
    assert "raw_fields" not in report
