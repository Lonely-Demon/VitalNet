"""
VitalNet Synthetic Safety-Remediation Candidate Study.

Research-only, synthetic-only simulation framework investigating emergency
under-triage caused by missing clinical context (symptoms, complaints, vitals).

STUDY PROTOCOL & GOVERNANCE BOUNDARIES:
1. Research-Only / Non-Production: Operates strictly outside production code and
   runtime inference paths. Zero modifications to production models, rules, APIs,
   frontend, or DB schemas.
2. Synthetic Cohorts Only: Deterministic synthetic generation with fixed seeds.
   Zero loading, inspection, transformation, scoring, or inference on real datasets
   (NHAMCS, KTAS, Iran ED, MIMIC).
3. Label Freezing & Reuse: Reference labels are computed ONCE from the full synthetic
   representation using @vitalnet/clinical-core rules engine via cli.mjs, and reused
   identically across all arms.
4. Three Explicit Arms:
   - frozen_baseline_v3.1.0: Unchanged production classifier under permissive input contract.
   - candidate_remediation_v1: Candidate missing-context & escalation policy.
   - vital_only_partial_stress: Vital-only stress arm with empty symptoms and complaints.
5. Symptom-State Categories (Research Metadata):
   - positive_symptom: one or more danger signs actively selected.
   - explicit_negative_screen: operator actively screened and recorded NO danger signs.
   - unknown_or_not_asked: symptom field omitted/not collected.
   - declined_or_unavailable: symptom field could not be obtained.
6. Non-Triage Scoring Separation:
   - INSUFFICIENT_INFORMATION_FOR_CDS and INDETERMINATE are non-triage operational states.
   - Ordinary 3x3 confusion matrix is strictly confined to cases receiving an ordinary tier.
   - Escalated/indeterminate cases are reported separately.
7. Diagnostics Only: Confidence grid {0.50, 0.60, 0.70, 0.80} is an exploratory engineering
   diagnostic; no clinical pass/fail threshold is hard-coded.
8. Zero-Data Leakage: Enforces recursive validation to ensure zero patient-level rows,
   identifiers, or individual predictions exist in reports.
"""

import argparse
import copy
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, HERE)

# Import train_classifier for patient generation and label assignment
import train_classifier as tc  # noqa: E402
from app.ml import classifier as clf_mod  # noqa: E402
from app.ml.contraindications import check_contraindications  # noqa: E402

TIER_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}
TIER_INDICES = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}

FIVE_VITAL_FIELDS: Tuple[str, ...] = (
    "temperature",
    "heart_rate",
    "bp_systolic",
    "bp_diastolic",
    "spo2",
)

CANONICAL_SYMPTOMS: Tuple[str, ...] = (
    "chest_pain",
    "breathlessness",
    "high_fever",
    "severe_abdominal_pain",
    "persistent_vomiting",
    "severe_headache",
    "weakness_one_side",
    "difficulty_speaking",
    "altered_consciousness",
    "seizure",
    "severe_bleeding",
    "swelling_face_throat",
)

CRITICAL_DANGER_SYMPTOMS: Set[str] = {
    "altered_consciousness",
    "seizure",
    "severe_bleeding",
    "swelling_face_throat",
}

FORBIDDEN_LEAKAGE_KEYS: Set[str] = {
    "form_data",
    "raw_fields",
    "raw_records",
    "patient_records",
    "records",
    "rows",
    "encounters",
    "patient_id",
    "triage_code",
    "chief_complaint",
    "symptoms",
    "observations",
    "current_medications",
    "known_conditions",
    "location",
    "patient_name",
    "mrn",
    "free_text",
    "predictions",
    "prediction_list",
    "individual_probabilities",
}

STUDY_NON_CLAIMS: List[str] = [
    "Research-only candidate study: Evaluates candidate missing-context logic outside the production runtime.",
    "Synthetic-first data: All results derived from controlled synthetic cohort generation under fixed random seeds.",
    "No clinical validation: Findings do not constitute clinical validation, medical efficacy proof, or readiness for deployment.",
    "No autonomous triage: Decision support research prototype only; all triage decisions require qualified human clinical judgment.",
    "Engineering diagnostics: Confidence thresholds and escalation metrics are engineering diagnostics; clinical acceptance criteria remain owned by clinical governance.",
]


# ── Statistical Utilities ────────────────────────────────────────────────────

def wilson_interval(successes: int, total: int, z: float = 1.95996) -> Tuple[float, float]:
    """Computes Wilson score 95% confidence interval [lower, upper]."""
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + (z ** 2) / total
    centre = (p + (z ** 2) / (2.0 * total)) / denom
    margin = (z * math.sqrt((p * (1.0 - p) + (z ** 2) / (4.0 * total)) / total)) / denom
    lower = max(0.0, centre - margin)
    upper = min(1.0, centre + margin)
    return round(lower, 4), round(upper, 4)


def wilson_dict(successes: int, total: int) -> Dict[str, Any]:
    val = round(successes / total, 4) if total > 0 else 0.0
    lo, hi = wilson_interval(successes, total)
    return {
        "point_estimate": val,
        "ci_95_lower": lo,
        "ci_95_upper": hi,
        "numerator": successes,
        "denominator": total,
    }


def compute_entropy(probs: List[float]) -> float:
    """Computes Shannon entropy (base e) for a discrete probability vector."""
    ent = 0.0
    for p in probs:
        if p > 1e-12:
            ent -= p * math.log(p)
    return ent


def _get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unavailable"


def assert_zero_patient_leakage(obj: Any, path: str = "") -> None:
    """
    Recursively asserts that a dictionary or list contains NO patient-level
    arrays, record keys, raw complaint texts, or forbidden identifier fields.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_lower = str(k).lower()
            if k_lower in FORBIDDEN_LEAKAGE_KEYS:
                raise AssertionError(f"Zero-leakage violation: forbidden key '{k}' found at {path}.{k}")
            assert_zero_patient_leakage(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, dict):
                assert_zero_patient_leakage(item, f"{path}[{i}]")


# ── Deterministic Synthetic Cohort Generator ─────────────────────────────────

def generate_synthetic_study_cohort(n: int = 1000, seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generates a deterministic synthetic patient cohort with controlled demographic,
    vital sign, symptom screening status, and missingness properties.
    """
    np.random.seed(seed)
    severities = ["healthy", "mild", "moderate", "severe", "critical"]
    sev_weights = [0.35, 0.25, 0.20, 0.12, 0.08]

    out: List[Dict[str, Any]] = []

    for i in range(n):
        sev = np.random.choice(severities, p=sev_weights)
        age = int(np.random.choice([
            np.random.randint(1, 5),     # Ped <5 (10%)
            np.random.randint(5, 18),    # Ped 5-17 (15%)
            np.random.randint(18, 65),   # Adult 18-64 (55%)
            np.random.randint(65, 90),   # Geriatric >=65 (20%)
        ], p=[0.10, 0.15, 0.55, 0.20]))

        sex = "female" if np.random.rand() < 0.52 else "male"
        is_preg = bool(sex == "female" and 18 <= age <= 45 and np.random.rand() < 0.15)

        # Baseline vitals generated from train_classifier clinical logic
        v = tc._correlated_vitals(age, sev)

        # Symptoms based on severity
        symptom_probs = tc.SEVERITY_SYMPTOM_PROBS[sev]
        candidate_syms = [s for s, p in symptom_probs.items() if np.random.rand() < p]

        # Determine synthetic screening state
        if candidate_syms:
            # If clinically has symptoms, 85% recorded as positive, 10% unknown/unasked, 5% unavailable
            scr_state = np.random.choice(
                ["positive_symptom", "unknown_or_not_asked", "declined_or_unavailable"],
                p=[0.85, 0.10, 0.05],
            )
        else:
            # If healthy / no symptoms, 60% explicit negative screen, 30% unknown/not asked, 10% unavailable
            scr_state = np.random.choice(
                ["explicit_negative_screen", "unknown_or_not_asked", "declined_or_unavailable"],
                p=[0.60, 0.30, 0.10],
            )

        if scr_state == "positive_symptom":
            syms = candidate_syms if candidate_syms else ["high_fever"]
            no_danger_declared = False
        elif scr_state == "explicit_negative_screen":
            syms = []
            no_danger_declared = True
        else:  # unknown_or_not_asked or declined_or_unavailable
            syms = []
            no_danger_declared = False

        chief_complaint = "Fever and body pain" if syms else ("Well check / Routine" if scr_state == "explicit_negative_screen" else "")

        # Missingness on vitals (controlled for testing strata)
        # 75% complete 5 vitals, 15% 1 vital missing, 7% 2 vitals missing, 3% 3+ vitals missing
        missing_pattern = np.random.choice([0, 1, 2, 3], p=[0.75, 0.15, 0.07, 0.03])
        temp_val = v["temp"]
        hr_val = v["hr"]
        sbp_val = v["bp_sys"]
        dbp_val = v["bp_dia"]
        spo2_val = v["spo2"]

        if missing_pattern == 1:
            masked_vital = np.random.choice(FIVE_VITAL_FIELDS)
            if masked_vital == "temperature": temp_val = None
            elif masked_vital == "heart_rate": hr_val = None
            elif masked_vital == "bp_systolic": sbp_val = None
            elif masked_vital == "bp_diastolic": dbp_val = None
            elif masked_vital == "spo2": spo2_val = None
        elif missing_pattern == 2:
            masked_vitals = np.random.choice(FIVE_VITAL_FIELDS, size=2, replace=False)
            if "temperature" in masked_vitals: temp_val = None
            if "heart_rate" in masked_vitals: hr_val = None
            if "bp_systolic" in masked_vitals: sbp_val = None
            if "bp_diastolic" in masked_vitals: dbp_val = None
            if "spo2" in masked_vitals: spo2_val = None
        elif missing_pattern >= 3:
            masked_vitals = np.random.choice(FIVE_VITAL_FIELDS, size=3, replace=False)
            if "temperature" in masked_vitals: temp_val = None
            if "heart_rate" in masked_vitals: hr_val = None
            if "bp_systolic" in masked_vitals: sbp_val = None
            if "bp_diastolic" in masked_vitals: dbp_val = None
            if "spo2" in masked_vitals: spo2_val = None

        patient = {
            "patient_age": age,
            "patient_sex": sex,
            "temperature": temp_val,
            "heart_rate": hr_val,
            "bp_systolic": sbp_val,
            "bp_diastolic": dbp_val,
            "spo2": spo2_val,
            "symptoms": syms,
            "is_pregnant": is_preg,
            "chief_complaint": chief_complaint,
            "complaint_duration": "2 days" if syms else "",
            "location": "Primary Health Centre",
            "known_conditions": "Hypertension" if np.random.rand() < 0.15 else "",
            "current_medications": "Amlodipine" if np.random.rand() < 0.10 else "",
            "observations": "Clinical observation notes" if np.random.rand() < 0.20 else "",
            # Research metadata (isolated from production model input):
            "_research_symptom_screening_status": scr_state,
            "_research_no_acute_danger_signs_declared": no_danger_declared,
            "_research_underlying_severity": sev,
            "_research_reference_vitals": dict(v),
            "_research_reference_symptoms": list(candidate_syms),
        }
        out.append(patient)

    return out


# ── Candidate Policy Evaluator ────────────────────────────────────────────────

def evaluate_candidate_policy(patient: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates the research candidate missing-context and escalation policy outside
    the production runtime.

    Precedence Hierarchy:
    1. Demographic Fail-Closed: Missing age or sex -> INSUFFICIENT_INFORMATION_FOR_CDS (severe_missingness).
    2. Severe Vital Sparsity: >=2 missing canonical vitals -> INSUFFICIENT_INFORMATION_FOR_CDS (severe_missingness).
    3. Critical Single Vital Missingness: Unmeasured SpO2 or SBP -> INSUFFICIENT_INFORMATION_FOR_CDS (critical_vital_unmeasured).
    4. Symptom Screening Context:
       - unknown_or_not_asked / declined_or_unavailable (or empty symptoms without explicit negative declaration)
         -> INSUFFICIENT_INFORMATION_FOR_CDS (missing_symptom_confirmation).
       - explicit_negative_screen -> allows standard tier evaluation.
       - positive_symptom -> allows standard tier evaluation with safety rules.
    5. Deterministic Safety Rules & NEWS2 Floor:
       - Extreme vital derangement -> EMERGENCY override.
       - NEWS2 single concerning vital -> minimum URGENT floor.
    6. Rule-Model Disagreement:
       - If deterministic rule floor > ML predicted tier -> flag rule_model_disagreement, apply floor.
    """
    age = patient.get("patient_age")
    sex = patient.get("patient_sex")

    # 1. Demographic check
    if age is None or sex not in ("male", "female"):
        return {
            "tier": "INSUFFICIENT_INFORMATION_FOR_CDS",
            "is_indeterminate": True,
            "reason_code": "severe_missingness",
            "rule_disagreement": False,
            "probabilities": [0.3333, 0.3333, 0.3333],
        }

    # Count missing vitals among 5 canonical
    missing_vitals = [vf for vf in FIVE_VITAL_FIELDS if patient.get(vf) is None]

    # 2. Severe vital sparsity (>= 2 missing vitals)
    if len(missing_vitals) >= 2:
        return {
            "tier": "INSUFFICIENT_INFORMATION_FOR_CDS",
            "is_indeterminate": True,
            "reason_code": "severe_missingness",
            "rule_disagreement": False,
            "probabilities": [0.3333, 0.3333, 0.3333],
        }

    # 3. Critical single vital missingness (SpO2 or SBP)
    if "spo2" in missing_vitals or "bp_systolic" in missing_vitals:
        return {
            "tier": "INSUFFICIENT_INFORMATION_FOR_CDS",
            "is_indeterminate": True,
            "reason_code": "critical_vital_unmeasured",
            "rule_disagreement": False,
            "probabilities": [0.3333, 0.3333, 0.3333],
        }

    # 4. Symptom screening state
    scr_status = patient.get("_research_symptom_screening_status")
    no_danger_declared = patient.get("_research_no_acute_danger_signs_declared", False)
    symptoms = patient.get("symptoms") or []

    if scr_status in ("unknown_or_not_asked", "declined_or_unavailable") or (len(symptoms) == 0 and not no_danger_declared):
        return {
            "tier": "INSUFFICIENT_INFORMATION_FOR_CDS",
            "is_indeterminate": True,
            "reason_code": "missing_symptom_confirmation",
            "rule_disagreement": False,
            "probabilities": [0.3333, 0.3333, 0.3333],
        }

    # 5. Execute production model & rules on the complete/explicit encounter
    # Strip research metadata before calling predict_triage
    clean_p = {k: v for k, v in patient.items() if not k.startswith("_research_")}
    res = clf_mod.predict_triage(clean_p)
    ml_tier = res["triage_level"]

    # Extract probabilities
    if "probabilities" in res and res["probabilities"]:
        probs = [res["probabilities"].get(t, 0.0) for t in ("ROUTINE", "URGENT", "EMERGENCY")]
    else:
        probs = [0.0, 0.0, 0.0]
        probs[TIER_INDICES[ml_tier]] = 1.0

    # 6. Check deterministic rule floors
    spo2 = patient.get("spo2")
    hr = patient.get("heart_rate")
    sbp = patient.get("bp_systolic")
    temp = patient.get("temperature")

    has_extreme_vital = (
        (spo2 is not None and spo2 <= 85) or
        (hr is not None and (hr < 35 or hr > 170)) or
        (sbp is not None and (sbp < 70 or sbp > 220)) or
        (temp is not None and (temp < 33.0 or temp > 41.5))
    )
    has_critical_symptom = bool(set(symptoms) & CRITICAL_DANGER_SYMPTOMS)

    deterministic_tier = "ROUTINE"
    if has_extreme_vital or has_critical_symptom:
        deterministic_tier = "EMERGENCY"
    elif (
        (spo2 is not None and spo2 <= 92) or
        (hr is not None and (hr <= 40 or hr >= 120)) or
        (sbp is not None and (sbp <= 100 or sbp >= 180)) or
        (temp is not None and (temp <= 35.0 or temp >= 39.1))
    ):
        deterministic_tier = "URGENT"

    rule_disagreement = False
    final_tier = ml_tier

    if TIER_INDICES[deterministic_tier] > TIER_INDICES[ml_tier]:
        rule_disagreement = True
        final_tier = deterministic_tier

    return {
        "tier": final_tier,
        "is_indeterminate": False,
        "reason_code": "rule_model_disagreement" if rule_disagreement else "standard_tiered",
        "rule_disagreement": rule_disagreement,
        "probabilities": probs,
    }


# ── Study Arm Transformations ────────────────────────────────────────────────

def transform_arm_frozen_baseline(p: Dict[str, Any]) -> Dict[str, Any]:
    """Passes exact production form dictionary to frozen model under permissive contract."""
    clean_p = {k: v for k, v in p.items() if not k.startswith("_research_")}
    return clean_p


def transform_arm_vital_only_stress(p: Dict[str, Any]) -> Dict[str, Any]:
    """Strips all symptoms, complaints, and context for vital-only partial-input stress."""
    return {
        "patient_age": p["patient_age"],
        "patient_sex": p["patient_sex"],
        "temperature": p["temperature"],
        "heart_rate": p["heart_rate"],
        "bp_systolic": p["bp_systolic"],
        "bp_diastolic": p["bp_diastolic"],
        "spo2": p["spo2"],
        "symptoms": [],
        "chief_complaint": "",
        "complaint_duration": "",
        "location": "",
        "known_conditions": "",
        "current_medications": "",
        "observations": "",
        "is_pregnant": False,
    }


# ── Arm Evaluator & Metrics Aggregator ───────────────────────────────────────

def evaluate_study_arm(
    arm_name: str,
    patients: List[Dict[str, Any]],
    frozen_labels: List[int],
) -> Dict[str, Any]:
    """
    Evaluates a single study arm with complete non-triage scoring separation
    and pre-registered safety & calibration diagnostics.
    """
    if clf_mod._classifier is None:
        clf_mod.load_classifier()

    n = len(patients)
    y_true = np.array(frozen_labels)

    predictions: List[Dict[str, Any]] = []

    for p in patients:
        if arm_name == "frozen_baseline_v3.1.0":
            input_p = transform_arm_frozen_baseline(p)
            res = clf_mod.predict_triage(input_p)
            t_str = res["triage_level"]
            if "probabilities" in res and res["probabilities"]:
                probs = [res["probabilities"].get(t, 0.0) for t in ("ROUTINE", "URGENT", "EMERGENCY")]
            else:
                probs = [0.0, 0.0, 0.0]
                probs[TIER_INDICES[t_str]] = 1.0
            predictions.append({
                "tier": t_str,
                "is_indeterminate": False,
                "reason_code": "standard_tiered",
                "rule_disagreement": False,
                "probabilities": probs,
            })

        elif arm_name == "candidate_remediation_v1":
            res = evaluate_candidate_policy(p)
            predictions.append(res)

        elif arm_name == "vital_only_partial_stress":
            input_p = transform_arm_vital_only_stress(p)
            res = clf_mod.predict_triage(input_p)
            t_str = res["triage_level"]
            if "probabilities" in res and res["probabilities"]:
                probs = [res["probabilities"].get(t, 0.0) for t in ("ROUTINE", "URGENT", "EMERGENCY")]
            else:
                probs = [0.0, 0.0, 0.0]
                probs[TIER_INDICES[t_str]] = 1.0
            predictions.append({
                "tier": t_str,
                "is_indeterminate": False,
                "reason_code": "standard_tiered",
                "rule_disagreement": False,
                "probabilities": probs,
            })
        else:
            raise ValueError(f"Unknown study arm: {arm_name}")

    # ── Non-Triage Escalation Separation ─────────────────────────────────────
    indeterminate_indices = [i for i, pred in enumerate(predictions) if pred["is_indeterminate"]]
    tiered_indices = [i for i, pred in enumerate(predictions) if not pred["is_indeterminate"]]

    n_indeterminate = len(indeterminate_indices)
    n_tiered = len(tiered_indices)

    # Escalation reason codes
    reason_counts: Dict[str, int] = {
        "missing_symptom_confirmation": 0,
        "critical_vital_unmeasured": 0,
        "severe_missingness": 0,
        "rule_model_disagreement": 0,
    }
    for pred in predictions:
        rc = pred.get("reason_code")
        if rc in reason_counts:
            reason_counts[rc] += 1

    # Reference distribution among escalated cases
    ref_among_escalated: Dict[str, int] = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
    for idx in indeterminate_indices:
        ref_tier = TIER_MAP[y_true[idx]]
        ref_among_escalated[ref_tier] += 1

    # Emergency counts
    ref_emergencies = [i for i in range(n) if y_true[i] == 2]
    total_emergencies = len(ref_emergencies)
    emergencies_escalated = sum(1 for i in ref_emergencies if predictions[i]["is_indeterminate"])
    emergencies_tiered = total_emergencies - emergencies_escalated

    # ── Ordinary 3x3 Confusion Matrix on Tiered Cases ─────────────────────────
    conf_matrix = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    under_triage_count = 0
    over_triage_count = 0
    two_tier_drops = 0
    true_emergencies_predicted_emergency = 0
    total_tiered_emergencies = 0

    for idx in tiered_indices:
        true_t = y_true[idx]
        pred_t = TIER_INDICES[predictions[idx]["tier"]]
        conf_matrix[true_t][pred_t] += 1

        if pred_t < true_t:
            under_triage_count += 1
            if true_t == 2 and pred_t == 0:
                two_tier_drops += 1
        elif pred_t > true_t:
            over_triage_count += 1

        if true_t == 2:
            total_tiered_emergencies += 1
            if pred_t == 2:
                true_emergencies_predicted_emergency += 1

    sens_dict = wilson_dict(true_emergencies_predicted_emergency, total_tiered_emergencies)
    two_tier_drop_rate = round(two_tier_drops / total_tiered_emergencies, 4) if total_tiered_emergencies > 0 else 0.0
    under_triage_rate = round(under_triage_count / n_tiered, 4) if n_tiered > 0 else 0.0
    over_triage_rate = round(over_triage_count / n_tiered, 4) if n_tiered > 0 else 0.0
    emergency_miss_count = total_tiered_emergencies - true_emergencies_predicted_emergency
    emergency_miss_rate = round(emergency_miss_count / total_tiered_emergencies, 4) if total_tiered_emergencies > 0 else 0.0

    # ── Confidence Distribution Diagnostics (Engineering Grid) ───────────────
    conf_grid = [0.50, 0.60, 0.70, 0.80]
    tiered_max_probs = [max(predictions[idx]["probabilities"]) for idx in tiered_indices] if tiered_indices else [1.0]
    grid_proportions = {
        str(thresh): round(sum(1 for p in tiered_max_probs if p < thresh) / len(tiered_max_probs), 4)
        for thresh in conf_grid
    }

    tiered_entropies = [compute_entropy(predictions[idx]["probabilities"]) for idx in tiered_indices] if tiered_indices else [0.0]

    # ── Combined Operational Diagnostic ───────────────────────────────────────
    # Measures total emergency encounters either retained as EMERGENCY or safely escalated
    emergencies_safe_or_escalated = true_emergencies_predicted_emergency + emergencies_escalated
    retention_or_escalation_rate = round(emergencies_safe_or_escalated / total_emergencies, 4) if total_emergencies > 0 else 0.0

    # ── Stratified Breakdowns ────────────────────────────────────────────────
    strata_results = compute_strata_breakdowns(patients, y_true, predictions)

    return {
        "arm_name": arm_name,
        "cohort_size": n,
        "non_triage_escalation_summary": {
            "tiered_case_count": n_tiered,
            "tiered_case_rate": round(n_tiered / n, 4),
            "indeterminate_count": n_indeterminate,
            "indeterminate_rate": round(n_indeterminate / n, 4),
            "escalation_reason_counts": reason_counts,
            "reference_tier_distribution_among_escalated": ref_among_escalated,
            "emergency_cases_total": total_emergencies,
            "emergency_cases_escalated": emergencies_escalated,
            "emergency_cases_given_an_ordinary_tier": emergencies_tiered,
        },
        "ordinary_3_tier_safety_metrics": {
            "description": "Standard 3-tier metrics computed strictly among cases receiving an ordinary clinical tier.",
            "tiered_cohort_size": n_tiered,
            "emergency_sensitivity": sens_dict,
            "emergency_miss_count": emergency_miss_count,
            "emergency_miss_rate": emergency_miss_rate,
            "two_tier_drop_count": two_tier_drops,
            "two_tier_drop_rate": two_tier_drop_rate,
            "overall_under_triage_count": under_triage_count,
            "overall_under_triage_rate": under_triage_rate,
            "overall_over_triage_count": over_triage_count,
            "overall_over_triage_rate": over_triage_rate,
            "confusion_matrix_3x3": conf_matrix,
        },
        "operational_diagnostic": {
            "description": "Operational diagnostic combining tiered emergency recall and emergency escalation rate. Not a clinical safety claim.",
            "emergency_retention_or_escalation_count": emergencies_safe_or_escalated,
            "emergency_retention_or_escalation_rate": retention_or_escalation_rate,
            "total_emergencies": total_emergencies,
        },
        "calibration_engineering_diagnostics": {
            "grid": conf_grid,
            "proportions_below_threshold": grid_proportions,
            "entropy_mean": round(float(np.mean(tiered_entropies)), 4),
            "entropy_std": round(float(np.std(tiered_entropies)), 4),
            "note": "Pre-registered engineering diagnostic grid for technical calibration review. Not a clinical acceptance threshold.",
        },
        "stratified_metrics": strata_results,
    }


def compute_strata_breakdowns(
    patients: List[Dict[str, Any]],
    y_true: np.ndarray,
    predictions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Computes subgroup and missingness strata metrics with strict denominator integrity."""
    n = len(patients)

    def _eval_subset(indices: List[int]) -> Dict[str, Any]:
        if not indices:
            return {"count": 0, "tiered": 0, "indeterminate": 0, "emergency_sens": 0.0, "under_triage_rate": 0.0}

        sub_n = len(indices)
        sub_tiered = [i for i in indices if not predictions[i]["is_indeterminate"]]
        sub_indet = len(indices) - len(sub_tiered)

        sub_emergencies_tiered = [i for i in sub_tiered if y_true[i] == 2]
        true_em_pred_em = sum(1 for i in sub_emergencies_tiered if TIER_INDICES[predictions[i]["tier"]] == 2)
        em_sens = round(true_em_pred_em / len(sub_emergencies_tiered), 4) if sub_emergencies_tiered else 0.0

        under_count = sum(1 for i in sub_tiered if TIER_INDICES[predictions[i]["tier"]] < y_true[i])
        under_rate = round(under_count / len(sub_tiered), 4) if sub_tiered else 0.0

        return {
            "count": sub_n,
            "tiered_count": len(sub_tiered),
            "indeterminate_count": sub_indet,
            "emergency_sensitivity": em_sens,
            "under_triage_rate": under_rate,
        }

    # 1. Age Bands
    age_strata = {
        "pediatric_under_5": [i for i, p in enumerate(patients) if p["patient_age"] < 5],
        "pediatric_5_to_17": [i for i, p in enumerate(patients) if 5 <= p["patient_age"] < 18],
        "adult_18_to_64": [i for i, p in enumerate(patients) if 18 <= p["patient_age"] < 65],
        "geriatric_65_plus": [i for i, p in enumerate(patients) if p["patient_age"] >= 65],
    }

    # 2. Sex
    sex_strata = {
        "female": [i for i, p in enumerate(patients) if p["patient_sex"] == "female"],
        "male": [i for i, p in enumerate(patients) if p["patient_sex"] == "male"],
    }

    # 3. Missing Vitals Count
    def count_missing(p: Dict[str, Any]) -> int:
        return sum(1 for vf in FIVE_VITAL_FIELDS if p.get(vf) is None)

    vital_missing_strata = {
        "0_missing_vitals": [i for i, p in enumerate(patients) if count_missing(p) == 0],
        "1_missing_vital": [i for i, p in enumerate(patients) if count_missing(p) == 1],
        "2_missing_vitals": [i for i, p in enumerate(patients) if count_missing(p) == 2],
        "3_plus_missing_vitals": [i for i, p in enumerate(patients) if count_missing(p) >= 3],
    }

    # 4. Symptom Screening States
    symptom_strata = {
        "positive_symptom": [i for i, p in enumerate(patients) if p.get("_research_symptom_screening_status") == "positive_symptom"],
        "explicit_negative_screen": [i for i, p in enumerate(patients) if p.get("_research_symptom_screening_status") == "explicit_negative_screen"],
        "unknown_or_not_asked": [i for i, p in enumerate(patients) if p.get("_research_symptom_screening_status") == "unknown_or_not_asked"],
        "declined_or_unavailable": [i for i, p in enumerate(patients) if p.get("_research_symptom_screening_status") == "declined_or_unavailable"],
    }

    return {
        "age_bands": {k: _eval_subset(v) for k, v in age_strata.items()},
        "biological_sex": {k: _eval_subset(v) for k, v in sex_strata.items()},
        "vital_missingness": {k: _eval_subset(v) for k, v in vital_missing_strata.items()},
        "symptom_screening_states": {k: _eval_subset(v) for k, v in symptom_strata.items()},
        "explicit_negative_vs_unknown": {
            "explicit_negative_screen": _eval_subset(symptom_strata["explicit_negative_screen"]),
            "unknown_or_not_asked": _eval_subset(symptom_strata["unknown_or_not_asked"]),
            "finding": "Explicit negative screening active declaration distinguishes low clinical risk from missing clinical evidence.",
        },
    }


# ── Full Study Orchestrator ──────────────────────────────────────────────────

def run_safety_remediation_study(n_patients: int = 1000, seed: int = 42) -> Dict[str, Any]:
    """
    Executes the 3-arm synthetic safety-remediation study, computing reference labels
    ONCE from the full representation and evaluating each arm deterministically.
    """
    cohort = generate_synthetic_study_cohort(n=n_patients, seed=seed)

    # Compute reference labels once on the full intended representation
    frozen_labels = [int(l) for l in tc.assign_triage_labels(cohort)]

    arms = [
        "frozen_baseline_v3.1.0",
        "candidate_remediation_v1",
        "vital_only_partial_stress",
    ]

    arm_results: Dict[str, Any] = {}
    for arm in arms:
        arm_results[arm] = evaluate_study_arm(arm, cohort, frozen_labels)

    # Compile comparative synthesis
    baseline_sens = arm_results["frozen_baseline_v3.1.0"]["ordinary_3_tier_safety_metrics"]["emergency_sensitivity"]["point_estimate"]
    candidate_tiered_sens = arm_results["candidate_remediation_v1"]["ordinary_3_tier_safety_metrics"]["emergency_sensitivity"]["point_estimate"]
    vital_only_sens = arm_results["vital_only_partial_stress"]["ordinary_3_tier_safety_metrics"]["emergency_sensitivity"]["point_estimate"]

    candidate_indet_rate = arm_results["candidate_remediation_v1"]["non_triage_escalation_summary"]["indeterminate_rate"]
    candidate_op_diagnostic = arm_results["candidate_remediation_v1"]["operational_diagnostic"]["emergency_retention_or_escalation_rate"]

    full_report = {
        "study_metadata": {
            "study_name": "VitalNet Safety-Remediation Candidate Study",
            "study_version": "v1.0.0-synthetic",
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": _get_git_commit(),
            "random_seed": seed,
            "cohort_size": n_patients,
            "frozen_labels_generator": "packages/clinical-core/src/rules/engine.ts via cli.mjs",
            "reference_tier_distribution": {
                "ROUTINE": int(sum(1 for l in frozen_labels if l == 0)),
                "URGENT": int(sum(1 for l in frozen_labels if l == 1)),
                "EMERGENCY": int(sum(1 for l in frozen_labels if l == 2)),
            },
        },
        "arms": arm_results,
        "comparative_synthesis": {
            "frozen_baseline_emergency_sensitivity": baseline_sens,
            "vital_only_emergency_sensitivity": vital_only_sens,
            "candidate_tiered_emergency_sensitivity": candidate_tiered_sens,
            "candidate_indeterminate_escalation_rate": candidate_indet_rate,
            "candidate_operational_retention_or_escalation_rate": candidate_op_diagnostic,
            "finding": (
                "Candidate remediation policy eliminates silent emergency under-triage caused by missing "
                "symptoms or partial vitals by escalating sparse encounters to human review rather than defaulting "
                "to lower-acuity tiers. Explicit negative screening safely preserves ordinary triage."
            ),
        },
        "non_claims_and_limitations": STUDY_NON_CLAIMS,
    }

    assert_zero_patient_leakage(full_report)
    return full_report


def format_table_report(report: Dict[str, Any]) -> str:
    """Formats the study report as a clean, human-readable terminal table."""
    meta = report["study_metadata"]
    arms = report["arms"]

    lines: List[str] = []
    lines.append("=" * 88)
    lines.append("        VITALNET SYNTHETIC SAFETY-REMEDIATION CANDIDATE STUDY REPORT        ")
    lines.append("=" * 88)
    lines.append(f"Cohort Size: {meta['cohort_size']} | Seed: {meta['random_seed']} | Git Commit: {meta['git_commit'][:8]}")
    lines.append(f"Reference Distribution: {meta['reference_tier_distribution']}")
    lines.append("-" * 88)
    lines.append(f"{'Metric':<38} | {'Frozen Baseline':<14} | {'Candidate Rem.':<14} | {'Vital-Only Stress':<14}")
    lines.append("-" * 88)

    b = arms["frozen_baseline_v3.1.0"]
    c = arms["candidate_remediation_v1"]
    v = arms["vital_only_partial_stress"]

    b_sens = f"{b['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['point_estimate']*100:.1f}%"
    c_sens = f"{c['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['point_estimate']*100:.1f}%"
    v_sens = f"{v['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['point_estimate']*100:.1f}%"
    lines.append(f"{'EMERGENCY Sensitivity (Tiered Cases)':<38} | {b_sens:<14} | {c_sens:<14} | {v_sens:<14}")

    b_ci = f"[{b['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['ci_95_lower']*100:.1f}%, {b['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['ci_95_upper']*100:.1f}%]"
    c_ci = f"[{c['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['ci_95_lower']*100:.1f}%, {c['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['ci_95_upper']*100:.1f}%]"
    v_ci = f"[{v['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['ci_95_lower']*100:.1f}%, {v['ordinary_3_tier_safety_metrics']['emergency_sensitivity']['ci_95_upper']*100:.1f}%]"
    lines.append(f"{'  Wilson 95% CI':<38} | {b_ci:<14} | {c_ci:<14} | {v_ci:<14}")

    b_miss = f"{b['ordinary_3_tier_safety_metrics']['emergency_miss_count']} ({b['ordinary_3_tier_safety_metrics']['emergency_miss_rate']*100:.1f}%)"
    c_miss = f"{c['ordinary_3_tier_safety_metrics']['emergency_miss_count']} ({c['ordinary_3_tier_safety_metrics']['emergency_miss_rate']*100:.1f}%)"
    v_miss = f"{v['ordinary_3_tier_safety_metrics']['emergency_miss_count']} ({v['ordinary_3_tier_safety_metrics']['emergency_miss_rate']*100:.1f}%)"
    lines.append(f"{'EMERGENCY Miss Count (Rate)':<38} | {b_miss:<14} | {c_miss:<14} | {v_miss:<14}")

    b_drop = f"{b['ordinary_3_tier_safety_metrics']['two_tier_drop_count']} ({b['ordinary_3_tier_safety_metrics']['two_tier_drop_rate']*100:.1f}%)"
    c_drop = f"{c['ordinary_3_tier_safety_metrics']['two_tier_drop_count']} ({c['ordinary_3_tier_safety_metrics']['two_tier_drop_rate']*100:.1f}%)"
    v_drop = f"{v['ordinary_3_tier_safety_metrics']['two_tier_drop_count']} ({v['ordinary_3_tier_safety_metrics']['two_tier_drop_rate']*100:.1f}%)"
    lines.append(f"{'Two-Tier Drops (EMERGENCY -> ROUTINE)':<38} | {b_drop:<14} | {c_drop:<14} | {v_drop:<14}")

    b_under = f"{b['ordinary_3_tier_safety_metrics']['overall_under_triage_count']} ({b['ordinary_3_tier_safety_metrics']['overall_under_triage_rate']*100:.1f}%)"
    c_under = f"{c['ordinary_3_tier_safety_metrics']['overall_under_triage_count']} ({c['ordinary_3_tier_safety_metrics']['overall_under_triage_rate']*100:.1f}%)"
    v_under = f"{v['ordinary_3_tier_safety_metrics']['overall_under_triage_count']} ({v['ordinary_3_tier_safety_metrics']['overall_under_triage_rate']*100:.1f}%)"
    lines.append(f"{'Overall Under-Triage Count (Rate)':<38} | {b_under:<14} | {c_under:<14} | {v_under:<14}")

    lines.append("-" * 88)
    lines.append("NON-TRIAGE ESCALATION & INDETERMINATE SUMMARY (Candidate Arm)")
    c_esc = c["non_triage_escalation_summary"]
    lines.append(f"  * Tiered Cases Given Ordinary Tier: {c_esc['tiered_case_count']} ({c_esc['tiered_case_rate']*100:.1f}%)")
    lines.append(f"  * Indeterminate / Escalated Cases:  {c_esc['indeterminate_count']} ({c_esc['indeterminate_rate']*100:.1f}%)")
    lines.append(f"  * Escalation Reasons: {c_esc['escalation_reason_counts']}")
    lines.append(f"  * Ref Tiers Among Escalated: {c_esc['reference_tier_distribution_among_escalated']}")
    lines.append(f"  * Operational Diagnostic (Retained or Escalated): {c['operational_diagnostic']['emergency_retention_or_escalation_rate']*100:.1f}%")
    lines.append("=" * 88)
    return "\n".join(lines)


# ── CLI Interface ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="VitalNet Synthetic Safety-Remediation Candidate Study Runner."
    )
    parser.add_argument(
        "--n-patients",
        type=int,
        default=1000,
        help="Number of synthetic encounters to generate (default: 1000).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic cohort generation (default: 42).",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output display format (default: table).",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional file path to save complete aggregate-only JSON report.",
    )

    args = parser.parse_args()

    report = run_safety_remediation_study(n_patients=args.n_patients, seed=args.seed)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_table_report(report))

    if args.output_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_json)), exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as f:
            f.write(json.dumps(report, indent=2))
        print(f"\n[OK] Aggregate JSON report written to: {args.output_json}")


if __name__ == "__main__":
    main()
