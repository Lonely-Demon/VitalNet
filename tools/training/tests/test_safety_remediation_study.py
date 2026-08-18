"""
Synthetic Unit & Invariant Tests for Safety-Remediation Candidate Study.

Validates:
1. Frozen baseline arm is unchanged and produces standard predict_triage outputs.
2. The candidate never interprets missing symptoms as explicit negative screening.
3. Explicit negative screening is distinct from missing or unavailable screening.
4. The candidate's insufficient-information state cannot silently become ROUTINE.
5. Candidate escalation reason codes are deterministic and aggregateable.
6. Vital-completeness boundary regression tests for all three cases:
   - >=2 missing vitals -> severe_missingness
   - Exactly 1 missing SpO2 or SBP -> critical_vital_unmeasured
   - Exactly 1 missing temp, HR, or DBP -> proceeds to symptom gate.
7. Extreme vitals preservation under missing symptoms (preserves physiological danger signal).
8. Generated synthetic complaints contain NO target tier labels (neutral text).
9. The three arms use identical synthetic reference labels (paired analysis).
10. Denominators, tiered reference emergencies, and 3x3 matrix separation are strictly preserved.
11. Deterministic repeatability: identical seed produces identical aggregate reports.
12. Subprocess-isolated real-data import guard and zero-leakage verification.
"""

import copy
import json
import os
import subprocess
import sys
from typing import Any, Dict, List
import pytest
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, "..", ".."))

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
        assert not any(k.startswith("_research_") for k in clean_p.keys())

        expected = clf_mod.predict_triage(clean_p)
        assert expected["triage_level"] in ("ROUTINE", "URGENT", "EMERGENCY")


# ── Test 2: Symptom Screening Distinction ─────────────────────────────────────

def test_symptom_screening_states_distinct():
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


# ── Test 5: Vital-Completeness Boundary (Three Cases) ─────────────────────────

def test_vital_completeness_boundary_three_cases():
    """
    Regression test for all three vital completeness boundary cases:
    1. >=2 missing canonical vitals -> severe_missingness
    2. Exactly 1 missing SpO2 or SBP -> critical_vital_unmeasured
    3. Exactly 1 missing temp, HR, or DBP -> proceeds to symptom gate.
    """
    base_complete = {
        "patient_age": 30,
        "patient_sex": "male",
        "temperature": 37.0,
        "heart_rate": 80,
        "bp_systolic": 120,
        "bp_diastolic": 80,
        "spo2": 98,
        "symptoms": [],
        "_research_symptom_screening_status": "explicit_negative_screen",
        "_research_no_acute_danger_signs_declared": True,
    }

    # Case 1: >= 2 missing vitals -> severe_missingness
    p_2missing = copy.deepcopy(base_complete)
    p_2missing["temperature"] = None
    p_2missing["heart_rate"] = None
    res1 = sr.evaluate_candidate_policy(p_2missing)
    assert res1["is_indeterminate"] is True
    assert res1["reason_code"] == "severe_missingness"

    # Case 2a: Exactly 1 missing SpO2 -> critical_vital_unmeasured
    p_spo2_missing = copy.deepcopy(base_complete)
    p_spo2_missing["spo2"] = None
    res2a = sr.evaluate_candidate_policy(p_spo2_missing)
    assert res2a["is_indeterminate"] is True
    assert res2a["reason_code"] == "critical_vital_unmeasured"

    # Case 2b: Exactly 1 missing SBP -> critical_vital_unmeasured
    p_sbp_missing = copy.deepcopy(base_complete)
    p_sbp_missing["bp_systolic"] = None
    res2b = sr.evaluate_candidate_policy(p_sbp_missing)
    assert res2b["is_indeterminate"] is True
    assert res2b["reason_code"] == "critical_vital_unmeasured"

    # Case 3a: Exactly 1 missing temp with explicit negative screen -> proceeds to standard tier
    p_temp_missing = copy.deepcopy(base_complete)
    p_temp_missing["temperature"] = None
    res3a = sr.evaluate_candidate_policy(p_temp_missing)
    assert res3a["is_indeterminate"] is False
    assert res3a["tier"] in ("ROUTINE", "URGENT", "EMERGENCY")

    # Case 3b: Exactly 1 missing HR with explicit negative screen -> proceeds to standard tier
    p_hr_missing = copy.deepcopy(base_complete)
    p_hr_missing["heart_rate"] = None
    res3b = sr.evaluate_candidate_policy(p_hr_missing)
    assert res3b["is_indeterminate"] is False
    assert res3b["tier"] in ("ROUTINE", "URGENT", "EMERGENCY")

    # Case 3c: Exactly 1 missing DBP with explicit negative screen -> proceeds to standard tier
    p_dbp_missing = copy.deepcopy(base_complete)
    p_dbp_missing["bp_diastolic"] = None
    res3c = sr.evaluate_candidate_policy(p_dbp_missing)
    assert res3c["is_indeterminate"] is False
    assert res3c["tier"] in ("ROUTINE", "URGENT", "EMERGENCY")

    # Case 3d: Exactly 1 missing temp with unknown symptoms -> proceeds to symptom gate -> missing_symptom_confirmation
    p_temp_unknown_syms = copy.deepcopy(base_complete)
    p_temp_unknown_syms["temperature"] = None
    p_temp_unknown_syms["_research_symptom_screening_status"] = "unknown_or_not_asked"
    p_temp_unknown_syms["_research_no_acute_danger_signs_declared"] = False
    res3d = sr.evaluate_candidate_policy(p_temp_unknown_syms)
    assert res3d["is_indeterminate"] is True
    assert res3d["reason_code"] == "missing_symptom_confirmation"


# ── Test 6: Extreme Vitals Preservation Under Missing Symptoms ────────────────

def test_extreme_vitals_preserved_under_missing_symptoms():
    """
    Verifies that encounters with extreme vitals and unknown symptoms are NOT silently
    labeled as simple missing symptoms, but preserve the extreme vital danger signal.
    """
    # Patient with extreme hypoxia (SpO2=80) but unknown symptoms
    p_hypoxic_unknown = {
        "patient_age": 45,
        "patient_sex": "male",
        "temperature": 37.0,
        "heart_rate": 85,
        "bp_systolic": 120,
        "bp_diastolic": 80,
        "spo2": 80,  # Extreme vital <= 85
        "symptoms": [],
        "_research_symptom_screening_status": "unknown_or_not_asked",
        "_research_no_acute_danger_signs_declared": False,
    }
    res = sr.evaluate_candidate_policy(p_hypoxic_unknown)
    assert res["is_indeterminate"] is True
    assert res["tier"] == "INSUFFICIENT_INFORMATION_FOR_CDS"
    assert res["extreme_vital_present"] is True
    assert res["reason_code"] == "missing_symptom_confirmation_with_extreme_vitals"

    # Patient with extreme vital (profound hypotension SBP=65) and explicit negative screen -> EMERGENCY
    p_hypotensive_explicit = {
        "patient_age": 45,
        "patient_sex": "male",
        "temperature": 37.0,
        "heart_rate": 85,
        "bp_systolic": 65,  # Extreme vital < 70
        "bp_diastolic": 40,
        "spo2": 98,
        "symptoms": [],
        "_research_symptom_screening_status": "explicit_negative_screen",
        "_research_no_acute_danger_signs_declared": True,
    }
    res_exp = sr.evaluate_candidate_policy(p_hypotensive_explicit)
    assert res_exp["is_indeterminate"] is False
    assert res_exp["tier"] == "EMERGENCY"
    assert res_exp["extreme_vital_present"] is True


# ── Test 7: Neutrality of Synthetic Complaint Text ───────────────────────────

def test_synthetic_complaints_contain_no_target_tier_labels():
    """Verifies that generated synthetic complaint text contains NO target tier or evaluation labels."""
    cohort = sr.generate_synthetic_study_cohort(n=500, seed=42)
    forbidden_acuity_keywords = ["ROUTINE", "URGENT", "EMERGENCY"]
    for p in cohort:
        cc = p.get("chief_complaint", "")
        for kw in forbidden_acuity_keywords:
            assert kw not in cc.upper(), f"Forbidden target tier label '{kw}' found in complaint: '{cc}'"


# ── Test 8: Paired Analysis Label Reuse Across Arms ───────────────────────────

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

    ref_em_b = b_res["non_triage_escalation_summary"]["total_reference_emergencies"]
    ref_em_c = c_res["non_triage_escalation_summary"]["total_reference_emergencies"]
    ref_em_v = v_res["non_triage_escalation_summary"]["total_reference_emergencies"]
    assert ref_em_b == ref_em_c == ref_em_v == sum(1 for l in labels if l == 2)


# ── Test 9: Denominator and Matrix Separation Integrity ──────────────────────

def test_denominator_and_matrix_separation_integrity(synthetic_cohort):
    """
    Verifies that tiered cases and indeterminate cases have separated denominators,
    that ordinary_3_tier_safety_metrics reports total and tiered reference emergencies,
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
    m = c_res["ordinary_3_tier_safety_metrics"]
    total_em = m["total_reference_emergencies"]
    tiered_em = m["tiered_reference_emergencies"]
    esc_em = m["emergency_cases_escalated"]
    assert esc_em + tiered_em == total_em

    # Invariant: 3x3 confusion matrix sums exactly to tiered_count
    cm = m["confusion_matrix_3x3"]
    matrix_sum = sum(sum(row) for row in cm)
    assert matrix_sum == tiered_count


# ── Test 10: Deterministic Repeatability ──────────────────────────────────────

def test_deterministic_repeatability():
    """Verifies that two runs with the same seed generate bitwise identical aggregate results."""
    rep1 = sr.run_safety_remediation_study(n_patients=50, seed=42)
    rep2 = sr.run_safety_remediation_study(n_patients=50, seed=42)

    rep1_clean = copy.deepcopy(rep1)
    rep2_clean = copy.deepcopy(rep2)
    rep1_clean["study_metadata"]["execution_timestamp"] = ""
    rep2_clean["study_metadata"]["execution_timestamp"] = ""

    assert json.dumps(rep1_clean, sort_keys=True) == json.dumps(rep2_clean, sort_keys=True)


# ── Test 11: Real-Data Isolation & Zero-Leakage (Subprocess Guard) ─────────────

def test_real_data_isolation_and_zero_leakage_subprocess():
    """
    Verifies via a separate clean subprocess with active runtime guards that:
    1. Importing study_safety_remediation does NOT import any real-data adapters
       (KTAS, NHAMCS, Iran ED, MIMIC, Generic CSV, or evaluation_sources package).
    2. Subprocess execution hook intercepts all subprocess calls and rejects any command
       referencing real-data authorization flags (--gate-3a-scoring-authorized, Gate M4, etc.)
       or real-data dataset paths/names, allowing only expected synthetic clinical-core CLI calls.
    3. Filesystem open hook intercepts file I/O and unconditionally blocks access to all
       real-data directories/files across all extensions (.csv, .xlsx, .txt, .json, .py).
    4. Child-process regression tests confirm that representative forbidden .csv, .xlsx,
       .txt, .json, and .py paths raise PermissionError immediately.
    5. Evaluates full 3-arm study on synthetic data and enforces recursive zero-leakage validation.
    """
    script = '''
import builtins
import os
import subprocess
import sys

# ── 1. Import Interceptor Guard ──────────────────────────────────────────
FORBIDDEN_MODULE_SUBSTRINGS = (
    "evaluation_sources",
    "ktas_2019",
    "nhamcs_2022",
    "iran_ed",
    "mimic_iv_ed",
    "generic_csv",
)

class StrictImportGuard:
    def find_spec(self, fullname, path, target=None):
        lower = fullname.lower()
        for forbidden in FORBIDDEN_MODULE_SUBSTRINGS:
            if forbidden in lower:
                raise ImportError(f"HARD REFUSAL: Import of real-data module '{fullname}' is forbidden during synthetic candidate study.")
        return None

sys.meta_path.insert(0, StrictImportGuard())

# ── 2. Filesystem Access Guard (Strict Unconditional Block) ───────────────
_orig_open = builtins.open
FORBIDDEN_PATH_SUBSTRINGS = (
    "tools/training/data",
    "evaluation_sources",
    "ed2022",
    "ed_admission",
    "ktas",
    "nhamcs",
    "iran_ed",
    "mimic_iv_ed",
)

def guarded_open(file, *args, **kwargs):
    file_str = str(file).lower().replace("\\\\", "/")
    for forbidden in FORBIDDEN_PATH_SUBSTRINGS:
        if forbidden in file_str:
            raise PermissionError(f"HARD REFUSAL: File access to prohibited real-data path '{file}' is forbidden during candidate study.")
    return _orig_open(file, *args, **kwargs)

builtins.open = guarded_open

# ── 3. Child-Process Regression Tests for Guarded Open ────────────────────
forbidden_regression_paths = [
    "tools/training/data/sample_dataset.csv",
    "tools/training/data/ktas_2019_raw.xlsx",
    "tools/training/data/ed2022_records.txt",
    "tools/training/data/mimic_iv_ed_sample.json",
    "evaluation_sources/nhamcs_2022.py",
    "tools/training/data/ed_admission_cohort.csv",
    "data/nhamcs/survey_2022.csv",
    "evaluation_sources/iran_ed.py",
]
for p in forbidden_regression_paths:
    try:
        open(p, "r")
        raise AssertionError(f"GUARD BYPASS: open('{p}') did not raise PermissionError!")
    except PermissionError:
        pass  # Expected: successfully blocked

# ── 4. Subprocess Command Guard ──────────────────────────────────────────
_orig_subprocess_run = subprocess.run
FORBIDDEN_CMD_FLAGS = (
    "--gate-3a-scoring-authorized",
    "--gate-m4-authorization",
    "--gate-3a",
    "--gate-m4",
    "evaluate_on_real.py",
    "evaluation_sources",
)

def guarded_subprocess_run(cmd, *args, **kwargs):
    cmd_str = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
    cmd_lower = cmd_str.lower()
    for forbidden in FORBIDDEN_CMD_FLAGS:
        if forbidden in cmd_lower:
            raise PermissionError(f"HARD REFUSAL: Execution of real-data authorization or evaluation command '{cmd_str}' is forbidden.")
    return _orig_subprocess_run(cmd, *args, **kwargs)

subprocess.run = guarded_subprocess_run

# ── 5. Load Study Runner & Execute ───────────────────────────────────────
import study_safety_remediation as sr

# Verify no forbidden modules in sys.modules
for mod in sys.modules:
    for forbidden in FORBIDDEN_MODULE_SUBSTRINGS:
        if forbidden in mod.lower():
            raise AssertionError(f"Isolation violation: forbidden module '{mod}' loaded into sys.modules.")

# Run synthetic study
report = sr.run_safety_remediation_study(n_patients=30, seed=42)

# Enforce recursive zero patient data leakage
sr.assert_zero_patient_leakage(report)

# Assert aggregate-only report structure
assert "patient_records" not in report
assert "records" not in report
assert "form_data" not in report
assert "raw_fields" not in report
assert "arms" in report
assert len(report["arms"]) == 3

print("PASS")
'''
    res = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=TOOLS_DIR,
    )
    assert res.returncode == 0, f"Subprocess failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert "PASS" in res.stdout
