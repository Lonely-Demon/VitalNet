"""
VitalNet NHAMCS Root-Cause Diagnostic & Synthetic Ablation Harness.

This module implements a frozen-model diagnostic framework designed to
systematically disentangle and quantify the four root-cause hypotheses
identified in the NHAMCS evaluation audit:

1. Proxy-Label Mismatch: IMMEDR arrival/waiting-time urgency vs physiological derangement.
2. Partial-Input Distribution Shift: Controlled 4-regime ablation on identical synthetic cohorts.
3. Missing-Vital Fallback Behavior: Controlled missing-vital impact across 0, 1, 2, and 3 missing vitals.
4. Runtime Architecture Comparison: Legacy Python backend classifier vs @vitalnet/clinical-core rules-first.

CRITICAL SAFETY & GOVERNANCE BOUNDARIES:
- Never alters classifier weights, thresholds, feature engineering, or rules.
- Freezes each synthetic patient's reference label BEFORE ablation; never recomputes labels on ablated data.
- Hardened --nhamcs-diagnostic mode is aggregate-only and strictly cannot score (never calls predict_triage or assignTier).
- One-pass streaming accumulator for real data; never constructs CanonicalPatientRecord or form_data for real records.
- Emits zero patient-level rows, IDs, form_data, text, or free-text fields in reports.
"""

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import types
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, HERE)

# Stub tree_export for train_classifier import if onnxruntime not present
_stub = types.ModuleType("tree_export")
_stub.onnx_to_tree_json = lambda *a, **k: None
_stub.evaluate_tree_json = lambda *a, **k: (None,)
sys.modules["tree_export"] = _stub

_spec = importlib.util.spec_from_file_location(
    "train_classifier", os.path.join(HERE, "train_classifier.py")
)
tc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tc)

from app.ml import classifier as clf_mod  # noqa: E402
from app.ml.clinical_features import ClinicalFeatureEngineer  # noqa: E402

TIER_MAP = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}
TIER_INDICES = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}

FIVE_VITAL_FIELDS: Tuple[str, ...] = (
    "temperature",
    "heart_rate",
    "bp_systolic",
    "bp_diastolic",
    "spo2",
)

IMMEDR_CAVEAT = (
    "IMMEDR caveat: CDC NHAMCS IMMEDR represents arrival immediacy and waiting-time priority "
    "assigned by ED triage nurses in a U.S. hospital setting, not an independently adjudicated "
    "clinical outcome or physiological triage tier. Mapping IMMEDR 1/2 to EMERGENCY, 3 to URGENT, "
    "and 4/5 to ROUTINE is a project-defined proxy for stress testing. Results do not constitute "
    "clinical validation, clinical safety evidence, or performance in the intended rural Indian PHC setting."
)

LIMITATIONS_AND_NON_CLAIMS: List[str] = [
    IMMEDR_CAVEAT,
    "Partial-input distribution shift: VitalNet was trained on multi-modal inputs (symptoms, complaints, context). "
    "Partial-input evaluation isolates vital-only inference outside the model's intended information regime.",
    "Frozen model contract: This diagnostic measures the existing frozen model and feature engineering without modification.",
    "Architecture comparison: Legacy Python backend and clinical-core rules-first are compared as parallel architectures, "
    "not as ground truth versus error.",
]

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
}


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


def _compute_file_sha256(file_path: str) -> Tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


# ── Core Invariant 1: Reference Label Freezing ────────────────────────────────

def freeze_synthetic_reference_labels(patients: List[Dict[str, Any]]) -> List[int]:
    """
    Computes and freezes ground-truth triage labels on the FULL synthetic patient representation
    using the authoritative rules engine (assign_triage_labels).
    These labels are frozen and NEVER recomputed after field blanking or ablation.
    """
    labels = tc.assign_triage_labels(patients)
    return [int(l) for l in labels]


# ── Core Invariant 2: Regime Transformations & Invariants ────────────────────

def to_full_input(patient: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a clean copy of the full synthetic patient with all fields intact."""
    return copy.deepcopy(patient)


def to_no_symptoms(patient: Dict[str, Any]) -> Dict[str, Any]:
    """
    Regime 2: Blank symptoms only.
    All other fields (chief_complaint, vitals, age, sex, duration, conditions, location) remain identical.
    """
    p = copy.deepcopy(patient)
    p["symptoms"] = []
    return p


def to_no_text(patient: Dict[str, Any]) -> Dict[str, Any]:
    """
    Regime 3: Retain vitals and structured symptoms.
    Blank complaint, duration, location, conditions, medications, and pregnancy context.
    """
    p = copy.deepcopy(patient)
    p["chief_complaint"] = ""
    p["complaint_duration"] = ""
    p["duration_days"] = 0
    p["location"] = ""
    p["known_conditions"] = ""
    p["current_medications"] = ""
    p["is_pregnant"] = False
    return p


def to_partial_input(patient: Dict[str, Any]) -> Dict[str, Any]:
    """
    Regime 4: Partial input (exact NHAMCS operational regime).
    Retain age, sex, temperature, heart_rate, bp_systolic, bp_diastolic, and spo2 ONLY.
    Blank symptoms, complaint, duration, location, conditions, medications, and context.
    Omit respiratory rate.
    """
    return {
        "patient_age": patient.get("patient_age"),
        "patient_sex": patient.get("patient_sex"),
        "temperature": patient.get("temperature"),
        "heart_rate": patient.get("heart_rate"),
        "bp_systolic": patient.get("bp_systolic"),
        "bp_diastolic": patient.get("bp_diastolic"),
        "spo2": patient.get("spo2"),
        "symptoms": [],
        "chief_complaint": "",
        "complaint_duration": "",
        "duration_days": 0,
        "location": "",
        "known_conditions": "",
        "current_medications": "",
        "is_pregnant": False,
    }


def assert_regime_invariants(
    patients_full: List[Dict[str, Any]],
    patients_ablated: List[Dict[str, Any]],
    regime_name: str,
) -> None:
    """
    Asserts that undeclared fields remain strictly identical between full and ablated cohorts,
    and declared ablated fields are strictly blanked or defaulted.
    """
    assert len(patients_full) == len(patients_ablated), "Cohort size mismatch"
    for i, (pf, pa) in enumerate(zip(patients_full, patients_ablated)):
        # Core demographic and vital fields must be identical across all regimes
        assert pf.get("patient_age") == pa.get("patient_age"), f"Age mismatch at index {i}"
        assert pf.get("patient_sex") == pa.get("patient_sex"), f"Sex mismatch at index {i}"
        for vf in FIVE_VITAL_FIELDS:
            assert pf.get(vf) == pa.get(vf), f"Vital {vf} mismatch at index {i}"

        if regime_name == "no_symptoms":
            assert pa.get("symptoms") == [], f"symptoms not empty in no_symptoms at index {i}"
            assert pf.get("chief_complaint") == pa.get("chief_complaint"), f"Complaint mismatch at index {i}"
            assert pf.get("complaint_duration") == pa.get("complaint_duration")
            assert pf.get("duration_days") == pa.get("duration_days")
            assert pf.get("location") == pa.get("location"), f"Location mismatch at index {i}"
            assert pf.get("known_conditions") == pa.get("known_conditions")
            assert pf.get("current_medications") == pa.get("current_medications")
            assert pf.get("is_pregnant") == pa.get("is_pregnant")

        elif regime_name == "no_text":
            assert pf.get("symptoms") == pa.get("symptoms"), f"Symptoms altered in no_text at index {i}"
            assert pa.get("chief_complaint") in ("", None), f"Complaint not blanked in no_text at index {i}"
            assert pa.get("complaint_duration") in ("", None), f"Duration not blanked in no_text at index {i}"
            assert pa.get("duration_days") == 0, f"Duration days not 0 in no_text at index {i}"
            assert pa.get("location") in ("", None), f"Location not blanked in no_text at index {i}"
            assert pa.get("known_conditions") in ("", [], None), f"Conditions not blanked in no_text at index {i}"
            assert pa.get("current_medications") in ("", [], None), f"Meds not blanked in no_text at index {i}"
            assert pa.get("is_pregnant") in (False, None), f"is_pregnant not False in no_text at index {i}"

        elif regime_name == "partial_input":
            assert pa.get("symptoms") == [], f"symptoms not empty in partial_input at index {i}"
            assert pa.get("chief_complaint") in ("", None), f"Complaint not blanked in partial_input at index {i}"
            assert pa.get("complaint_duration") in ("", None), f"Duration not blanked in partial_input at index {i}"
            assert pa.get("duration_days") == 0, f"Duration days not 0 in partial_input at index {i}"
            assert pa.get("location") in ("", None), f"Location not blanked in partial_input at index {i}"
            assert pa.get("known_conditions") in ("", [], None), f"Conditions not blanked in partial_input at index {i}"
            assert pa.get("current_medications") in ("", [], None), f"Meds not blanked in partial_input at index {i}"
            assert pa.get("is_pregnant") in (False, None), f"is_pregnant not False in partial_input at index {i}"
            assert "respiratory_rate" not in pa or pa.get("respiratory_rate") is None, (
                f"respiratory_rate present in partial_input at index {i}"
            )


# ── Synthetic 4-Regime Controlled Ablation Runner ────────────────────────────

def run_synthetic_regime_ablation(
    patients_full: List[Dict[str, Any]],
    frozen_labels: List[int],
) -> Dict[str, Any]:
    """
    Evaluates the frozen model across the four controlled input regimes using identical frozen labels.
    """
    if clf_mod._classifier is None:
        clf_mod.load_classifier()

    regimes = {
        "full_input": [to_full_input(p) for p in patients_full],
        "no_symptoms": [to_no_symptoms(p) for p in patients_full],
        "no_text": [to_no_text(p) for p in patients_full],
        "partial_input": [to_partial_input(p) for p in patients_full],
    }

    # Verify invariants for each regime
    for r_name, r_patients in regimes.items():
        if r_name != "full_input":
            assert_regime_invariants(patients_full, r_patients, r_name)

    n = len(patients_full)
    y_true = np.array(frozen_labels)
    results: Dict[str, Any] = {}

    for r_name, r_patients in regimes.items():
        preds: List[int] = []
        raw_preds: List[int] = []
        safety_net_triggers = 0
        news2_floor_triggers = 0
        probs_list: List[List[float]] = []

        for p in r_patients:
            res = clf_mod.predict_triage(p)
            tier_idx = TIER_INDICES[res["triage_level"]]
            preds.append(tier_idx)

            if "probabilities" in res and res["probabilities"]:
                probs = [res["probabilities"].get(t, 0.0) for t in ("ROUTINE", "URGENT", "EMERGENCY")]
            elif res.get("safety_net_triggered"):
                probs = [0.0, 0.0, 1.0]
            else:
                probs = [0.0, 0.0, 0.0]
                probs[tier_idx] = 1.0
            probs_list.append(probs)

            if res.get("safety_net_triggered"):
                safety_net_triggers += 1
            if res.get("news2_floor_triggered"):
                news2_floor_triggers += 1

            # Raw model prediction
            feat_map = clf_mod._feature_engineer.engineer_features(p)
            feat_vec = [feat_map.get(k, 0.0) for k in tc.FEATURE_NAMES]
            raw_tier = int(clf_mod._classifier.predict([feat_vec])[0])
            raw_preds.append(raw_tier)

        y_pred = np.array(preds)
        y_raw = np.array(raw_preds)
        probs_arr = np.array(probs_list)

        # Confusion Matrix
        cm = [[int(((y_true == r) & (y_pred == c)).sum()) for c in range(3)] for r in range(3)]

        # Class sensitivities
        sensitivities: Dict[str, Any] = {}
        for t, t_name in TIER_MAP.items():
            tot_t = int((y_true == t).sum())
            tp_t = int(((y_true == t) & (y_pred == t)).sum())
            sensitivities[t_name] = wilson_dict(tp_t, tot_t)

        under_triage_count = int((y_pred < y_true).sum())
        over_triage_count = int((y_pred > y_true).sum())
        exact_agree_count = int((y_pred == y_true).sum())

        em_cases = int((y_true == 2).sum())
        em_missed_as_routine = int(((y_true == 2) & (y_pred == 0)).sum())
        em_under_triaged = int(((y_true == 2) & (y_pred < 2)).sum())

        results[r_name] = {
            "total_encounters": n,
            "overall_accuracy": round(exact_agree_count / n, 4) if n > 0 else 0.0,
            "confusion_matrix": cm,
            "tier_sensitivities": sensitivities,
            "under_triage_rate": round(under_triage_count / n, 4) if n > 0 else 0.0,
            "under_triage_count": under_triage_count,
            "over_triage_rate": round(over_triage_count / n, 4) if n > 0 else 0.0,
            "over_triage_count": over_triage_count,
            "emergency_under_triage": {
                "total_emergency_cases": em_cases,
                "under_triaged_count": em_under_triaged,
                "under_triaged_pct": round((em_under_triaged / em_cases) * 100.0, 2) if em_cases > 0 else 0.0,
                "missed_as_routine_count": em_missed_as_routine,
                "missed_as_routine_pct": round((em_missed_as_routine / em_cases) * 100.0, 2) if em_cases > 0 else 0.0,
            },
            "predicted_tier_distribution": {
                "ROUTINE": int((y_pred == 0).sum()),
                "URGENT": int((y_pred == 1).sum()),
                "EMERGENCY": int((y_pred == 2).sum()),
                "ROUTINE_pct": round(float((y_pred == 0).mean()) * 100.0, 2),
                "URGENT_pct": round(float((y_pred == 1).mean()) * 100.0, 2),
                "EMERGENCY_pct": round(float((y_pred == 2).mean()) * 100.0, 2),
            },
            "mean_class_probabilities": {
                "ROUTINE": round(float(probs_arr[:, 0].mean()), 4),
                "URGENT": round(float(probs_arr[:, 1].mean()), 4),
                "EMERGENCY": round(float(probs_arr[:, 2].mean()), 4),
            },
            "safety_net_activation_count": safety_net_triggers,
            "safety_net_activation_rate": round(safety_net_triggers / n, 4) if n > 0 else 0.0,
            "news2_floor_activation_count": news2_floor_triggers,
            "news2_floor_activation_rate": round(news2_floor_triggers / n, 4) if n > 0 else 0.0,
            "raw_model_accuracy": round(float((y_raw == y_true).mean()), 4) if n > 0 else 0.0,
        }

    # Calculate deltas relative to full_input
    base = results["full_input"]
    deltas: Dict[str, Any] = {}
    for r_name in ("no_symptoms", "no_text", "partial_input"):
        curr = results[r_name]
        deltas[r_name] = {
            "accuracy_drop": round(base["overall_accuracy"] - curr["overall_accuracy"], 4),
            "emergency_sensitivity_drop": round(
                base["tier_sensitivities"]["EMERGENCY"]["point_estimate"]
                - curr["tier_sensitivities"]["EMERGENCY"]["point_estimate"],
                4,
            ),
            "under_triage_increase": round(curr["under_triage_rate"] - base["under_triage_rate"], 4),
            "routine_prediction_shift_pct": round(
                curr["predicted_tier_distribution"]["ROUTINE_pct"]
                - base["predicted_tier_distribution"]["ROUTINE_pct"],
                2,
            ),
        }

    return {
        "regimes": results,
        "ablation_deltas_vs_full_input": deltas,
    }


# ── Missing-Vital Neutral Sensitivity Analysis ───────────────────────────────

def run_missing_vital_analysis(
    patients_full: List[Dict[str, Any]],
    frozen_labels: List[int],
    seed: int = 2026,
) -> Dict[str, Any]:
    """
    Evaluates the neutral impact of missing vital signs on the frozen model in partial_input mode.
    Constructs cohorts with 0, 1, 2, and 3 missing vitals by deterministically masking the five
    model-used vitals from complete synthetic patients, reusing original frozen labels.
    """
    if clf_mod._classifier is None:
        clf_mod.load_classifier()

    # Filter to patients who have all 5 vitals complete in original generation
    complete_patients: List[Dict[str, Any]] = []
    complete_labels: List[int] = []
    for p, l in zip(patients_full, frozen_labels):
        if all(p.get(k) is not None for k in FIVE_VITAL_FIELDS):
            complete_patients.append(to_partial_input(p))
            complete_labels.append(l)

    n_comp = len(complete_patients)
    if n_comp == 0:
        return {"error": "No complete synthetic patients found for missing-vital analysis"}

    y_true = np.array(complete_labels)

    # Deterministic missingness patterns
    single_vital_patterns = [(k,) for k in FIVE_VITAL_FIELDS]
    pair_vital_patterns = [
        ("bp_systolic", "bp_diastolic"),
        ("temperature", "heart_rate"),
        ("spo2", "heart_rate"),
        ("bp_systolic", "heart_rate"),
        ("spo2", "bp_systolic"),
    ]
    triplet_vital_patterns = [
        ("bp_systolic", "bp_diastolic", "heart_rate"),
        ("temperature", "heart_rate", "spo2"),
        ("bp_systolic", "spo2", "temperature"),
        ("bp_diastolic", "heart_rate", "spo2"),
    ]

    missingness_levels = {
        "0_missing_vitals": [copy.deepcopy(p) for p in complete_patients],
        "1_missing_vital": [],
        "2_missing_vitals": [],
        "3_missing_vitals": [],
    }

    # Generate deterministic 1-missing, 2-missing, and 3-missing cohorts
    for idx, p in enumerate(complete_patients):
        # 1 missing
        p1 = copy.deepcopy(p)
        pat1 = single_vital_patterns[idx % len(single_vital_patterns)]
        for k in pat1:
            p1[k] = None
        missingness_levels["1_missing_vital"].append(p1)

        # 2 missing
        p2 = copy.deepcopy(p)
        pat2 = pair_vital_patterns[idx % len(pair_vital_patterns)]
        for k in pat2:
            p2[k] = None
        missingness_levels["2_missing_vitals"].append(p2)

        # 3 missing
        p3 = copy.deepcopy(p)
        pat3 = triplet_vital_patterns[idx % len(triplet_vital_patterns)]
        for k in pat3:
            p3[k] = None
        missingness_levels["3_missing_vitals"].append(p3)

    results: Dict[str, Any] = {}

    for lvl_name, lvl_patients in missingness_levels.items():
        preds: List[int] = []
        probs_list: List[List[float]] = []
        safety_net_triggers = 0
        news2_floor_triggers = 0

        # Feature shift metrics
        derived_feature_diffs: List[float] = []

        for orig_p, mut_p in zip(complete_patients, lvl_patients):
            res = clf_mod.predict_triage(mut_p)
            tier_idx = TIER_INDICES[res["triage_level"]]
            preds.append(tier_idx)

            if "probabilities" in res and res["probabilities"]:
                probs = [res["probabilities"].get(t, 0.0) for t in ("ROUTINE", "URGENT", "EMERGENCY")]
            elif res.get("safety_net_triggered"):
                probs = [0.0, 0.0, 1.0]
            else:
                probs = [0.0, 0.0, 0.0]
                probs[tier_idx] = 1.0
            probs_list.append(probs)

            if res.get("safety_net_triggered"):
                safety_net_triggers += 1
            if res.get("news2_floor_triggered"):
                news2_floor_triggers += 1

            # Quantify feature engineer fallback effect
            feat_orig = clf_mod._feature_engineer.engineer_features(orig_p)
            feat_mut = clf_mod._feature_engineer.engineer_features(mut_p)
            for k in ("shock_index", "pulse_pressure", "mean_arterial_pressure", "temp_deviation"):
                diff = abs(feat_orig.get(k, 0.0) - feat_mut.get(k, 0.0))
                derived_feature_diffs.append(diff)

        y_pred = np.array(preds)
        probs_arr = np.array(probs_list)

        tot_em = int((y_true == 2).sum())
        tp_em = int(((y_true == 2) & (y_pred == 2)).sum())
        under_triage = int((y_pred < y_true).sum())
        over_triage = int((y_pred > y_true).sum())
        exact_agree = int((y_pred == y_true).sum())

        results[lvl_name] = {
            "cohort_encounters": n_comp,
            "overall_agreement": round(exact_agree / n_comp, 4),
            "emergency_sensitivity": wilson_dict(tp_em, tot_em),
            "under_triage_rate": round(under_triage / n_comp, 4),
            "under_triage_count": under_triage,
            "over_triage_rate": round(over_triage / n_comp, 4),
            "over_triage_count": over_triage,
            "predicted_tier_distribution": {
                "ROUTINE": int((y_pred == 0).sum()),
                "URGENT": int((y_pred == 1).sum()),
                "EMERGENCY": int((y_pred == 2).sum()),
                "ROUTINE_pct": round(float((y_pred == 0).mean()) * 100.0, 2),
                "URGENT_pct": round(float((y_pred == 1).mean()) * 100.0, 2),
                "EMERGENCY_pct": round(float((y_pred == 2).mean()) * 100.0, 2),
            },
            "mean_class_probabilities": {
                "ROUTINE": round(float(probs_arr[:, 0].mean()), 4),
                "URGENT": round(float(probs_arr[:, 1].mean()), 4),
                "EMERGENCY": round(float(probs_arr[:, 2].mean()), 4),
            },
            "safety_net_activation_count": safety_net_triggers,
            "safety_net_activation_rate": round(safety_net_triggers / n_comp, 4),
            "news2_floor_activation_count": news2_floor_triggers,
            "news2_floor_activation_rate": round(news2_floor_triggers / n_comp, 4),
            "mean_derived_vital_feature_shift": round(float(np.mean(derived_feature_diffs)), 4) if derived_feature_diffs else 0.0,
        }

    return {
        "cohort_size": n_comp,
        "missingness_levels": results,
    }


# ── Architecture Comparison Runner ───────────────────────────────────────────

def run_architecture_comparison(
    patients_full: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compares the legacy Python FastAPI backend classifier (ML-primary + guardrails)
    against @vitalnet/clinical-core rules-first (assignTier) under full_input and partial_input.
    Treats both as architectures to compare rather than ground truth versus error.
    """
    if clf_mod._classifier is None:
        clf_mod.load_classifier()

    regimes = {
        "full_input": [to_full_input(p) for p in patients_full],
        "partial_input": [to_partial_input(p) for p in patients_full],
    }

    results: Dict[str, Any] = {}
    n = len(patients_full)

    for r_name, r_patients in regimes.items():
        # 1. Legacy Backend predictions
        legacy_preds = [TIER_INDICES[clf_mod.predict_triage(p)["triage_level"]] for p in r_patients]
        # 2. clinical-core rules-first predictions via CLI bridge
        rules_first_preds = tc.assign_triage_labels(r_patients)

        y_leg = np.array(legacy_preds)
        y_rf = np.array(rules_first_preds)

        cm = [[int(((y_rf == rf) & (y_leg == leg)).sum()) for leg in range(3)] for rf in range(3)]
        agree_count = int((y_leg == y_rf).sum())
        leg_higher_count = int((y_leg > y_rf).sum())
        rf_higher_count = int((y_rf > y_leg).sum())

        results[r_name] = {
            "total_encounters": n,
            "agreement_count": agree_count,
            "agreement_rate": round(agree_count / n, 4) if n > 0 else 0.0,
            "divergence": {
                "legacy_more_conservative_count": leg_higher_count,
                "legacy_more_conservative_rate": round(leg_higher_count / n, 4) if n > 0 else 0.0,
                "rules_first_more_conservative_count": rf_higher_count,
                "rules_first_more_conservative_rate": round(rf_higher_count / n, 4) if n > 0 else 0.0,
            },
            "cross_architecture_matrix": {
                "description": "Rows: clinical-core rules_first tier (0=ROUTINE, 1=URGENT, 2=EMERGENCY). "
                               "Cols: legacy backend classifier tier (0=ROUTINE, 1=URGENT, 2=EMERGENCY).",
                "matrix": cm,
            },
            "legacy_distribution": {
                "ROUTINE": int((y_leg == 0).sum()),
                "URGENT": int((y_leg == 1).sum()),
                "EMERGENCY": int((y_leg == 2).sum()),
                "ROUTINE_pct": round(float((y_leg == 0).mean()) * 100.0, 2),
                "URGENT_pct": round(float((y_leg == 1).mean()) * 100.0, 2),
                "EMERGENCY_pct": round(float((y_leg == 2).mean()) * 100.0, 2),
            },
            "rules_first_distribution": {
                "ROUTINE": int((y_rf == 0).sum()),
                "URGENT": int((y_rf == 1).sum()),
                "EMERGENCY": int((y_rf == 2).sum()),
                "ROUTINE_pct": round(float((y_rf == 0).mean()) * 100.0, 2),
                "URGENT_pct": round(float((y_rf == 1).mean()) * 100.0, 2),
                "EMERGENCY_pct": round(float((y_rf == 2).mean()) * 100.0, 2),
            },
        }

    return results


# ── Hardened --nhamcs-diagnostic (Streaming Aggregate-Only, Non-Scoring) ─────

def run_nhamcs_diagnostic(file_path: str) -> Dict[str, Any]:
    """
    Performs a streaming, one-pass aggregate-only diagnostic on CDC NHAMCS 2022 encounters.
    STRICT NON-SCORING & AGGREGATE-ONLY INVARIANTS:
    - Never calls NHAMCS2022Source.load_for_evaluation().
    - Never constructs CanonicalPatientRecord, form_data, or raw_fields objects.
    - Never loads classifier model weights or runs predict_triage().
    - Never calls clinical-core assignTier() on real data.
    - Never emits patient-level records, rows, IDs, form_data, predictions, probabilities, or text.
    - Produces purely aggregate distributions and derangement cross-tabulations.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"NHAMCS fixed-width file not found at: {file_path}")

    file_sha256, file_size_bytes = _compute_file_sha256(file_path)

    # Immediacy code mapping (1/2 -> EMERGENCY, 3 -> URGENT, 4/5 -> ROUTINE)
    immedr_map = {1: 2, 2: 2, 3: 1, 4: 0, 5: 0}

    total_records = 0
    valid_records = 0
    excluded_records = 0
    exclusion_reasons: Dict[str, int] = {}

    def _exclude(reason: str):
        nonlocal excluded_records
        exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
        excluded_records += 1

    proxy_counts = {0: 0, 1: 0, 2: 0}
    vital_complete_count = 0

    cross_tab: Dict[str, Dict[str, Any]] = {}
    for t_idx, t_name in TIER_MAP.items():
        cross_tab[t_name] = {
            "total_proxy_encounters": 0,
            "any_severe_vital_derangement_count": 0,
            "normal_or_mild_vitals_count": 0,
            "derangement_by_type": {
                "severe_hypotension_or_crisis_bp": 0,
                "severe_tachycardia_or_bradycardia": 0,
                "severe_hypoxemia_spo2_under_90": 0,
                "extreme_temperature": 0,
                "shock_index_over_1": 0,
            },
        }

    with open(file_path, "r", encoding="latin-1") as f:
        for line in f:
            total_records += 1
            line_clean = line.rstrip("\r\n")

            if len(line_clean) < 68:
                _exclude("short_line_format")
                continue

            # 1. Age (Cols 16-18, [15:18])
            raw_age = line_clean[15:18].strip()
            if not raw_age or raw_age in ("-9", "-8"):
                _exclude("invalid_age")
                continue
            try:
                age_int = int(raw_age)
                if not (0 <= age_int <= 94):
                    _exclude("invalid_age")
                    continue
            except ValueError:
                _exclude("invalid_age")
                continue

            # 2. Sex (Col 25, [24:25])
            raw_sex = line_clean[24:25].strip()
            if raw_sex not in ("1", "2"):
                _exclude("invalid_sex")
                continue

            # 3. IMMEDR (Cols 67-68, [66:68])
            raw_immedr = line_clean[66:68].strip()
            if raw_immedr == "-9":
                _exclude("sentinel_immedr_minus_9")
                continue
            elif raw_immedr == "-8":
                _exclude("sentinel_immedr_minus_8")
                continue
            elif raw_immedr in ("0", "00"):
                _exclude("sentinel_immedr_0")
                continue
            elif raw_immedr in ("7", "07"):
                _exclude("sentinel_immedr_7")
                continue
            else:
                try:
                    code_val = int(raw_immedr)
                    if code_val in immedr_map:
                        ref_tier = immedr_map[code_val]
                    else:
                        _exclude("sentinel_immedr_out_of_range")
                        continue
                except ValueError:
                    _exclude("sentinel_immedr_invalid")
                    continue

            # 4. Temperature (Cols 48-51, [47:51])
            raw_temp = line_clean[47:51].strip()
            temperature = None
            if raw_temp and raw_temp not in ("-9", "-8", "9999"):
                try:
                    temp_val = int(raw_temp)
                    if 896 <= temp_val <= 1056:
                        temperature = round(((temp_val / 10.0) - 32.0) * 5.0 / 9.0, 1)
                except ValueError:
                    temperature = None

            # 5. Pulse (Cols 52-54, [51:54])
            raw_pulse = line_clean[51:54].strip()
            heart_rate = None
            if raw_pulse and raw_pulse not in ("-9", "-8", "998"):
                try:
                    pulse_val = int(raw_pulse)
                    if 0 <= pulse_val <= 240:
                        heart_rate = pulse_val
                except ValueError:
                    heart_rate = None

            # 6. SBP (Cols 58-60, [57:60])
            raw_sbp = line_clean[57:60].strip()
            bp_systolic = None
            if raw_sbp and raw_sbp not in ("-9", "-8", "0", "000"):
                try:
                    sbp_val = int(raw_sbp)
                    if 43 <= sbp_val <= 289:
                        bp_systolic = sbp_val
                except ValueError:
                    bp_systolic = None

            # 7. DBP (Cols 61-63, [60:63])
            raw_dbp = line_clean[60:63].strip()
            bp_diastolic = None
            if raw_dbp and raw_dbp not in ("-9", "-8", "0", "000", "998"):
                try:
                    dbp_val = int(raw_dbp)
                    if 22 <= dbp_val <= 190:
                        bp_diastolic = dbp_val
                except ValueError:
                    bp_diastolic = None

            # BP inversion check
            if bp_systolic is not None and bp_diastolic is not None:
                if bp_diastolic >= bp_systolic:
                    bp_systolic = None
                    bp_diastolic = None

            # 8. SpO2 (Cols 64-66, [63:66])
            raw_spo2 = line_clean[63:66].strip()
            spo2 = None
            if raw_spo2 and raw_spo2 not in ("-9", "-8"):
                try:
                    o2_val = int(raw_spo2)
                    if 0 <= o2_val <= 100:
                        spo2 = o2_val
                except ValueError:
                    spo2 = None

            # Count valid included encounter
            valid_records += 1
            proxy_counts[ref_tier] += 1
            t_name = TIER_MAP[ref_tier]
            cross_tab[t_name]["total_proxy_encounters"] += 1

            if (temperature is not None and heart_rate is not None and
                bp_systolic is not None and bp_diastolic is not None and spo2 is not None):
                vital_complete_count += 1

            # Vital Derangement Evaluation
            is_bp_deranged = bp_systolic is not None and (bp_systolic < 90 or bp_systolic > 200)
            is_hr_deranged = heart_rate is not None and (heart_rate < 45 or heart_rate > 135)
            is_spo2_deranged = spo2 is not None and spo2 < 90
            is_temp_deranged = temperature is not None and (temperature < 35.0 or temperature > 39.5)
            is_shock_deranged = (heart_rate is not None and bp_systolic is not None and bp_systolic > 0 and (heart_rate / bp_systolic) > 1.0)

            any_deranged = is_bp_deranged or is_hr_deranged or is_spo2_deranged or is_temp_deranged or is_shock_deranged

            if is_bp_deranged:
                cross_tab[t_name]["derangement_by_type"]["severe_hypotension_or_crisis_bp"] += 1
            if is_hr_deranged:
                cross_tab[t_name]["derangement_by_type"]["severe_tachycardia_or_bradycardia"] += 1
            if is_spo2_deranged:
                cross_tab[t_name]["derangement_by_type"]["severe_hypoxemia_spo2_under_90"] += 1
            if is_temp_deranged:
                cross_tab[t_name]["derangement_by_type"]["extreme_temperature"] += 1
            if is_shock_deranged:
                cross_tab[t_name]["derangement_by_type"]["shock_index_over_1"] += 1

            if any_deranged:
                cross_tab[t_name]["any_severe_vital_derangement_count"] += 1
            else:
                cross_tab[t_name]["normal_or_mild_vitals_count"] += 1

    if valid_records == 0:
        raise ValueError("NHAMCS file parsed 0 valid records")

    # Compute percentages
    for t_name, data in cross_tab.items():
        tot = data["total_proxy_encounters"]
        der = data["any_severe_vital_derangement_count"]
        norm = data["normal_or_mild_vitals_count"]
        data["severe_vital_derangement_pct"] = round((der / tot) * 100.0, 2) if tot > 0 else 0.0
        data["normal_or_mild_vitals_pct"] = round((norm / tot) * 100.0, 2) if tot > 0 else 0.0

    source_manifest = {
        "source_id": "nhamcs_2022",
        "source_name": "CDC NHAMCS 2022 Emergency Department Summary (ed2022)",
        "version": "2022 Public Use File",
        "official_url": "https://www.cdc.gov/nchs/nhamcs/documentation/index.html",
        "license_note": "CDC Public Use Data Agreement (100% de-identified)",
        "file_sha256": file_sha256,
        "file_size_bytes": file_size_bytes,
        "input_mode": "partial_input",
        "label_definition": "nhamcs_immediacy_v1: IMMEDR 1/2 -> EMERGENCY, 3 -> URGENT, 4/5 -> ROUTINE (stress-test proxy only)",
        "scoring_supported": False,
        "execution_mode": "nhamcs_diagnostic",
    }

    report = {
        "execution_mode": "nhamcs_diagnostic",
        "evaluation_provenance": {
            "evaluation_git_commit": _get_git_commit(),
            "evaluation_harness_version": "1.0.0",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        },
        "source_manifest": source_manifest,
        "dataset_summary": {
            "source_id": source_manifest["source_id"],
            "source_name": source_manifest["source_name"],
            "total_records_parsed": total_records,
            "valid_records_analyzed": valid_records,
            "excluded_records": excluded_records,
            "exclusion_breakdown": exclusion_reasons,
            "complete_five_vitals_count": vital_complete_count,
            "complete_five_vitals_pct": round((vital_complete_count / valid_records) * 100.0, 2) if valid_records > 0 else 0.0,
        },
        "proxy_tier_breakdown": {
            "EMERGENCY": {
                "count": proxy_counts[2],
                "pct": round((proxy_counts[2] / valid_records) * 100.0, 2),
                "definition": "IMMEDR 1 (Resuscitation) or 2 (Emergent: <14 min)",
            },
            "URGENT": {
                "count": proxy_counts[1],
                "pct": round((proxy_counts[1] / valid_records) * 100.0, 2),
                "definition": "IMMEDR 3 (Urgent: 15-60 min)",
            },
            "ROUTINE": {
                "count": proxy_counts[0],
                "pct": round((proxy_counts[0] / valid_records) * 100.0, 2),
                "definition": "IMMEDR 4 (Semi-urgent) or 5 (Non-urgent)",
            },
        },
        "proxy_vs_vital_derangement_cross_tabulation": cross_tab,
        "limitations_and_non_claims": LIMITATIONS_AND_NON_CLAIMS,
    }

    assert_zero_patient_leakage(report)
    return report


# ── Zero Patient Leakage Assertion ───────────────────────────────────────────

def assert_zero_patient_leakage(report: Dict[str, Any]) -> None:
    """Recursively validates that report contains zero patient-level data or forbidden keys."""
    def _check(obj: Any, path: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                k_lower = str(k).lower()
                if k_lower in FORBIDDEN_LEAKAGE_KEYS:
                    raise AssertionError(f"Patient-level key '{k}' found at path '{path}'")
                _check(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _check(item, f"{path}[{i}]")

    _check(report)


# ── CLI & Orchestration ──────────────────────────────────────────────────────

def generate_synthetic_cohort(n: int, seed: int = 2026) -> List[Dict[str, Any]]:
    """Generates out-of-sample synthetic patients with all fields."""
    np.random.seed(seed)
    severities = ["healthy", "mild", "moderate", "severe", "critical"]
    weights = [0.30, 0.22, 0.22, 0.16, 0.10]
    pediatric_fraction = 0.22
    out = []
    for _ in range(n):
        sev = np.random.choice(severities, p=weights)
        ped = np.random.random() < pediatric_fraction
        p = tc.generate_patient(sev, pediatric=ped)
        # Ensure known_conditions and medications are strings to prevent lower() errors
        if isinstance(p.get("known_conditions"), list):
            p["known_conditions"] = ", ".join(p["known_conditions"])
        if isinstance(p.get("current_medications"), list):
            p["current_medications"] = ", ".join(p["current_medications"])
        out.append(p)
    return out


def build_full_synthetic_diagnostic_report(
    n: int = 5000,
    seed: int = 2026,
) -> Dict[str, Any]:
    """Orchestrates the full synthetic diagnostic suite."""
    print(f"\n[1/4] Generating {n} synthetic patients (seed={seed})...")
    patients_full = generate_synthetic_cohort(n=n, seed=seed)

    print("[2/4] Freezing reference labels on full input via clinical-core rules engine...")
    frozen_labels = freeze_synthetic_reference_labels(patients_full)

    print("[3/4] Running 4-regime controlled ablation...")
    ablation_results = run_synthetic_regime_ablation(patients_full, frozen_labels)

    print("[4/4] Running missing-vital sensitivity analysis...")
    missing_vital_results = run_missing_vital_analysis(patients_full, frozen_labels, seed=seed)

    print("Running cross-architecture parity comparison (Legacy vs Rules-First)...")
    arch_results = run_architecture_comparison(patients_full)

    report = {
        "execution_mode": "synthetic_diagnostic",
        "evaluation_provenance": {
            "evaluation_git_commit": _get_git_commit(),
            "evaluation_harness_version": "1.0.0",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        },
        "diagnostic_config": {
            "sample_size": n,
            "random_seed": seed,
        },
        "regime_ablation": ablation_results,
        "missing_vital_sensitivity": missing_vital_results,
        "architecture_comparison": arch_results,
        "limitations_and_non_claims": LIMITATIONS_AND_NON_CLAIMS,
    }

    assert_zero_patient_leakage(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VitalNet NHAMCS Root-Cause Diagnostic & Synthetic Ablation Harness"
    )
    parser.add_argument(
        "--synthetic-ablation",
        action="store_true",
        default=True,
        help="Run 4-regime synthetic ablation and missing-vital analysis (default)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=5000,
        help="Number of synthetic patients for ablation (default: 5000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Random seed (default: 2026)",
    )
    parser.add_argument(
        "--nhamcs-diagnostic",
        type=str,
        default=None,
        metavar="PATH",
        help="Run aggregate-only non-scoring NHAMCS vital derangement cross-tabulation",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to write aggregate JSON diagnostic report",
    )

    args = parser.parse_args()

    if args.nhamcs_diagnostic:
        print(f"\nRunning aggregate-only NHAMCS diagnostic on: {args.nhamcs_diagnostic}")
        report = run_nhamcs_diagnostic(args.nhamcs_diagnostic)
    else:
        report = build_full_synthetic_diagnostic_report(n=args.n, seed=args.seed)

    if args.json_out:
        out_dir = os.path.dirname(args.json_out)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nDiagnostic report saved to: {args.json_out}")

    print("\nDiagnostic execution completed successfully.")


if __name__ == "__main__":
    main()
