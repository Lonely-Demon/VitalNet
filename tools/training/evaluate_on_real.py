"""
VitalNet External Validation and Inspection Harness.

Evaluates VitalNet's triage classifier against external public emergency department
datasets (e.g. Iran ED inspection-only, CDC NHAMCS 2022 partial-input mode, generic CSV)
or synthetic self-tests with strict aggregate-only reporting, zero patient-level data leakage,
comprehensive discrimination metrics (sensitivity, specificity, PPV, NPV with Wilson 95% CIs),
safety under-triage tracking, guardrail lift analysis, and diagnostic calibration ECE.

Usage Examples:
    # 1. Source Inspection Mode (Aggregate Data Quality):
    python tools/training/evaluate_on_real.py --inspect-source iran-ed --file data/iran_ed.csv --linkage-file data/ED_admission.csv --json-out outputs/iran_inspection.json
    python tools/training/evaluate_on_real.py --inspect-source nhamcs-2022 --file data/ed2022.txt --json-out outputs/nhamcs_inspection.json

    # 2. Evaluation Mode (Partial-Input for NHAMCS 2022):
    python tools/training/evaluate_on_real.py --dataset nhamcs-2022 --file data/ed2022.txt --json-out outputs/nhamcs_evaluation.json

    # 3. Iran ED Evaluation Refusal (Strict Non-Zero Exit):
    python tools/training/evaluate_on_real.py --dataset iran-ed --file data/iran_ed.csv

    # 4. Backward-Compatible Self-Test Mode (Proves Machinery):
    python tools/training/evaluate_on_real.py --self-test

    # 5. Backward-Compatible Generic CSV Mode:
    python tools/training/evaluate_on_real.py --csv data/mimic_ed.csv --acuity-scale esi --temp-fahrenheit
"""

import argparse
import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
import types
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Evaluation sources adapter imports
from evaluation_sources import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    ExclusionCounters,
    GenericCSVSource,
    IranEDSource,
    NHAMCS2022Source,
    SourceManifest,
    SyntheticSelfTestSource,
    TIER_INDICES,
    TIER_NAMES,
    compute_file_sha256,
    get_evaluation_source,
)
from evaluation_sources.generic_csv import (
    ACUITY_MAPS,
    ALLOWED_SYMPTOMS,
    parse_reference_tier,
    row_to_formdata,
)
from evaluation_sources.iran_ed import EXACT_REFUSAL_MESSAGE

from app.ml import classifier as clf_mod  # noqa: E402

TIER = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}
TIER_NAME = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}

# Canonical five vital sign fields for completeness auditing and subgroup slicing
FIVE_VITAL_FIELDS: Tuple[str, ...] = (
    "temperature",
    "heart_rate",
    "bp_systolic",
    "bp_diastolic",
    "spo2",
)

LIMITATIONS_AND_NON_CLAIMS: List[str] = [
    "Cohort-specific proxy evaluation: Results reflect dataset-specific population characteristics and triage proxy mapping conventions.",
    "Non-equivalence to clinical safety evidence: Does not constitute medical device clearance, prospective clinical trial evidence, or rural/ASHA validation.",
    "Partial-input caveat: Evaluated with partial inputs (e.g. missing or empty free-text complaints/symptoms), reflecting vital-sign-driven inference only.",
    "Calibration diagnostic note: Calibration metric (ECE) represents predicted-class confidence vs empirical correctness diagnostic, not full multi-class clinical probability calibration.",
    "Survey weighting policy: CDC NHAMCS survey expansion weights (PATWT) are excluded from model discrimination, confusion matrix, and safety metrics calculations.",
]

FORBIDDEN_LEAKAGE_KEYS = {
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

def _get_evaluation_provenance() -> Dict[str, str]:
    """
    Returns metadata about the model version, Git commit, and evaluation harness version.
    Must execute purely locally with no network calls.
    """
    model_path = os.path.join(BACKEND_DIR, "app", "ml", "models", "triage_classifier.pkl")
    if os.path.exists(model_path):
        mtime = os.path.getmtime(model_path)
        iso_ts = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        model_version = f"triage_classifier.pkl@{iso_ts}"
    else:
        model_version = "unavailable"

    try:
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], 
            cwd=PROJECT_ROOT, 
            stderr=subprocess.DEVNULL, 
            text=True
        ).strip()
        evaluation_git_commit = commit_hash
    except Exception:
        evaluation_git_commit = "unavailable"

    return {
        "model_version": model_version,
        "evaluation_git_commit": evaluation_git_commit,
        "evaluation_harness_version": "1.0.0",
    }


# ── Strict Zero-Leakage Assertion ────────────────────────────────────────────

def assert_zero_patient_leakage(obj: Any, path: str = "root") -> None:
    """
    Recursively inspects a JSON-serializable report object to strictly guarantee
    that ZERO patient-level records, raw rows, free-text strings, patient identifiers,
    or individual predictions are present in the final output.
    """
    if isinstance(obj, dict):
        # In field_missingness / missingness_by_field dictionaries, keys are dataset column headers,
        # not patient record fields containing individual patient values.
        is_missingness_dict = path.endswith("field_missingness") or path.endswith("missingness_by_field")
        for k, v in obj.items():
            k_lower = str(k).lower()
            if not is_missingness_dict and k_lower in FORBIDDEN_LEAKAGE_KEYS:
                raise AssertionError(
                    f"Zero patient-level data leakage violation: forbidden key '{k}' found at {path}.{k}"
                )
            assert_zero_patient_leakage(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            assert_zero_patient_leakage(item, f"{path}[{idx}]")


# ── Statistics & Diagnostic Metrics ──────────────────────────────────────────

def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float, float]:
    """Wilson score interval for a binomial proportion. Returns (p, lo, hi)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def wilson_dict(k: int, n: int, z: float = 1.96) -> Dict[str, Any]:
    """Returns a dict with point estimate, 95% CI bounds, counts, and formatted string."""
    p, lo, hi = wilson(k, n, z)
    if n == 0 or math.isnan(p):
        return {
            "point": None,
            "ci_lower": None,
            "ci_upper": None,
            "k": k,
            "n": n,
            "formatted": "   n/a   ",
        }
    return {
        "point": round(p, 4),
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
        "k": k,
        "n": n,
        "formatted": f"{p:5.3f} [{lo:.3f}-{hi:.3f}]",
    }


def _fmt_ci(k: int, n: int) -> str:
    return wilson_dict(k, n)["formatted"]


def expected_calibration_error(
    conf: np.ndarray, correct: np.ndarray, n_bins: int = 10
) -> Tuple[float, List[Tuple[float, float, int, float, float]]]:
    """
    Expected Calibration Error (ECE) and bin summary tuples:
    (lo, hi, count, mean_conf, accuracy).
    NOTE: Limited diagnostic of predicted-class confidence vs correctness;
    does not represent full clinical probability calibration.
    """
    ece, n = 0.0, len(conf)
    rows = []
    if n == 0:
        return 0.0, rows
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        mask = (conf > lo) & (conf <= hi)
        m = int(mask.sum())
        if m == 0:
            continue
        acc = float(correct[mask].mean())
        avg_conf = float(conf[mask].mean())
        ece += (m / n) * abs(acc - avg_conf)
        rows.append((lo, hi, m, avg_conf, acc))
    return float(ece), rows


def _confusion(y_ref: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    cm = np.zeros((3, 3), dtype=int)
    for r, p in zip(y_ref, y_pred):
        cm[r, p] += 1
    return cm


# ── Backward Compatibility Helpers ───────────────────────────────────────────

def _get(row: Dict[str, Any], *names: str, default: Any = None) -> Any:
    for nm in names:
        if nm in row and str(row[nm]).strip() != "":
            return row[nm]
    return default


def _num(v: Any, cast=float) -> Optional[Any]:
    if v is None or str(v).strip() == "":
        return None
    try:
        return cast(float(v))
    except (ValueError, TypeError):
        return None


def _sex(v: Any) -> str:
    s = str(v or "").strip().lower()
    if s in ("m", "male", "1"):
        return "male"
    if s in ("f", "female", "0"):
        return "female"
    return "other"


def reference_tier(row: Dict[str, Any], acuity_scale: Optional[str] = "esi") -> Optional[int]:
    ref_label = parse_reference_tier(row, acuity_scale)
    if ref_label is not None and ref_label in TIER_INDICES:
        return TIER_INDICES[ref_label]
    return None


def load_csv(path: str, acuity_scale: str = "esi", temp_fahrenheit: bool = False):
    source = GenericCSVSource(
        file_path=path, acuity_scale=acuity_scale, temp_fahrenheit=temp_fahrenheit
    )
    records, counters, _ = source.load_for_evaluation(file_path=path)
    formdatas = [r.form_data for r in records]
    y_ref = np.array([r.reference_tier_index for r in records], dtype=int)
    if counters.reasons.get("unusable_reference", 0) > 0:
        print(f"[note] dropped {counters.reasons['unusable_reference']} row(s) with no usable reference label")
    return formdatas, y_ref


def self_test(n: int = 8000):
    """Harness self-test on synthetic patients — PROVES THE MACHINERY ONLY."""
    source = SyntheticSelfTestSource(n=n, seed=2026)
    records, _, _ = source.load_for_evaluation()
    formdatas = [r.form_data for r in records]
    y_ref = np.array([r.reference_tier_index for r in records], dtype=int)
    print("\n" + "!" * 74)
    print("!! SELF-TEST MODE — reference = clinical-core's rules engine (the same")
    print("!! rule the model was trained on). This validates the HARNESS, not the")
    print("!! model. These numbers are NOT clinical validation.")
    print("!" * 74 + "\n")
    return formdatas, y_ref


# ── Inspection Pipeline ───────────────────────────────────────────────────────

def _print_inspection_report(data_quality: AggregateDataQuality) -> None:
    manifest = data_quality.source_manifest
    print("=" * 74)
    print(f"DATASET INSPECTION REPORT  —  {manifest.source_name}")
    print("=" * 74)
    print(f"Source ID:          {manifest.source_id}")
    print(f"Version:            {manifest.version}")
    print(f"Official URL:       {manifest.official_url}")
    print(f"License:            {manifest.license_note}")
    print(f"SHA-256 Checksum:   {manifest.file_sha256 or 'N/A'}")
    print(f"Input Mode:         {manifest.input_mode}")
    print(f"Scoring Supported:  {manifest.scoring_supported}")
    print(f"Total Records:      {data_quality.total_records_inspected}")

    if data_quality.headers_present:
        print(f"\nHeaders Present ({len(data_quality.headers_present)}):")
        print("  " + ", ".join(data_quality.headers_present))

    if data_quality.missingness_by_field:
        print("\nField Missingness:")
        print(f"  {'Field':28} {'Valid Count':>12} {'Missing Count':>15} {'Missing %':>12}")
        print("  " + "-" * 69)
        for field_name, stats in data_quality.missingness_by_field.items():
            print(
                f"  {field_name:28} {stats.get('valid_count', 0):12d} "
                f"{stats.get('missing_count', 0):15d} {stats.get('missing_pct', 0.0):11.2f}%"
            )

    if data_quality.vital_distributions:
        print("\nVital Distributions:")
        print(f"  {'Vital':20} {'Valid Count':>12} {'Mean':>10} {'Min':>10} {'Max':>10} {'Missing %':>12}")
        print("  " + "-" * 68)
        for vital_name, vstats in data_quality.vital_distributions.items():
            mean_str = f"{vstats['mean']:.2f}" if vstats.get("mean") is not None else "N/A"
            min_str = f"{vstats['min']:.1f}" if vstats.get("min") is not None else "N/A"
            max_str = f"{vstats['max']:.1f}" if vstats.get("max") is not None else "N/A"
            print(
                f"  {vital_name:20} {vstats.get('valid_count', 0):12d} {mean_str:>10} "
                f"{min_str:>10} {max_str:>10} {vstats.get('missingness_pct', 0.0):11.2f}%"
            )

    print("\n5-Vital Completeness (SBP, DBP, HR, Temp, SpO2):")
    print(
        f"  Complete encounters: {data_quality.complete_vitals_count} "
        f"({data_quality.complete_vitals_pct:.2f}%)"
    )

    if data_quality.reference_distribution:
        print("\nReference Triage / Acuity Distribution:")
        for k, v in data_quality.reference_distribution.items():
            print(f"  {str(k):25}: {v:8d}")

    if data_quality.linkage_summary:
        print("\nAdmission Key Linkage Summary:")
        for lk, lv in data_quality.linkage_summary.items():
            print(f"  {str(lk):25}: {lv}")

    if data_quality.exclusion_summary:
        print("\nExclusion Summary:")
        for rk, rv in data_quality.exclusion_summary.items():
            print(f"  {str(rk):30}: {rv:8d}")

    print("\nLimitations & Non-Claims:")
    for claim in LIMITATIONS_AND_NON_CLAIMS:
        print(f"  * {claim}")

    print("\n" + "=" * 74)


def build_inspection_json_report(data_quality: AggregateDataQuality) -> Dict[str, Any]:
    manifest_dict = data_quality.source_manifest.to_dict()
    total = data_quality.total_records_inspected
    excluded = sum(data_quality.exclusion_summary.values())
    valid = total - excluded if total >= excluded else total

    return {
        "source_manifest": manifest_dict,
        "evaluation_provenance": _get_evaluation_provenance(),
        "execution_mode": "inspection",
        "cohort_flow": {
            "total_records": total,
            "valid_records": valid,
            "excluded_records": excluded,
            "exclusions_by_reason": data_quality.exclusion_summary,
        },
        "data_quality": {
            "total_records_inspected": total,
            "headers_present": data_quality.headers_present,
            "field_missingness": data_quality.missingness_by_field,
            "vital_ranges": data_quality.vital_distributions,
            "triage_distribution": data_quality.reference_distribution,
            "complete_vitals_count": data_quality.complete_vitals_count,
            "complete_vitals_pct": data_quality.complete_vitals_pct,
            "linkage_summary": data_quality.linkage_summary,
            "extra_metadata": data_quality.extra_metadata,
        },
        "limitations_and_non_claims": LIMITATIONS_AND_NON_CLAIMS,
    }


def run_inspection(
    source_id: str,
    file_path: Optional[str] = None,
    linkage_file_path: Optional[str] = None,
    patients_file_path: Optional[str] = None,
    edstays_file_path: Optional[str] = None,
    medrecon_file_path: Optional[str] = None,
    exploratory_medrecon_inspection: bool = False,
    cohort_policy: str = "all_stays",
    json_out: Optional[str] = None,
    acuity_scale: str = "esi",
    temp_fahrenheit: bool = False,
) -> AggregateDataQuality:
    source = get_evaluation_source(
        source_id=source_id,
        file_path=file_path,
        linkage_file_path=linkage_file_path,
        patients_file_path=patients_file_path,
        edstays_file_path=edstays_file_path,
        medrecon_file_path=medrecon_file_path,
        exploratory_medrecon_inspection=exploratory_medrecon_inspection,
        cohort_policy=cohort_policy,
        acuity_scale=acuity_scale,
        temp_fahrenheit=temp_fahrenheit,
    )
    data_quality = source.inspect(
        file_path=file_path,
        linkage_file_path=linkage_file_path,
        patients_file_path=patients_file_path,
        edstays_file_path=edstays_file_path,
        medrecon_file_path=medrecon_file_path,
        exploratory_medrecon_inspection=exploratory_medrecon_inspection,
    )
    _print_inspection_report(data_quality)

    if json_out:
        report_dict = build_inspection_json_report(data_quality)
        assert_zero_patient_leakage(report_dict)
        out_dir = os.path.dirname(json_out)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
        print(f"\nAggregate-only JSON inspection report saved to: {json_out}")

    return data_quality



# ── Evaluation Pipeline ───────────────────────────────────────────────────────

def calculate_evaluation_metrics(
    y_ref: np.ndarray,
    y_prod: np.ndarray,
    y_raw: np.ndarray,
    conf: np.ndarray,
    guardrail: np.ndarray,
    formdatas: List[Dict[str, Any]],
) -> Dict[str, Any]:
    n = len(y_ref)
    cm = _confusion(y_ref, y_prod)
    cm_list = [[int(cm[r, c]) for c in range(3)] for r in range(3)]
    acc = float((y_prod == y_ref).mean()) if n > 0 else 0.0

    # Discrimination per tier
    discrimination: Dict[str, Dict[str, Any]] = {}
    for t in (0, 1, 2):
        tier_name = TIER_NAMES[t]
        tp = int(((y_ref == t) & (y_prod == t)).sum())
        fn = int(((y_ref == t) & (y_prod != t)).sum())
        fp = int(((y_ref != t) & (y_prod == t)).sum())
        tn = int(((y_ref != t) & (y_prod != t)).sum())

        discrimination[tier_name] = {
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "sensitivity": wilson_dict(tp, tp + fn),
            "specificity": wilson_dict(tn, tn + fp),
            "ppv": wilson_dict(tp, tp + fp),
            "npv": wilson_dict(tn, tn + fn),
        }

    # Safety metrics
    under = int((y_prod < y_ref).sum())
    over = int((y_prod > y_ref).sum())
    em_mask = y_ref == 2
    em_total = int(em_mask.sum())
    em_miss = int((em_mask & (y_prod < 2)).sum())
    em_to_routine = int((em_mask & (y_prod == 0)).sum())

    urg_mask = y_ref == 1
    urg_total = int(urg_mask.sum())
    urg_to_routine = int((urg_mask & (y_prod == 0)).sum())

    safety_metrics = {
        "overall_under_triage_count": under,
        "overall_under_triage": wilson_dict(under, n),
        "overall_over_triage_count": over,
        "overall_over_triage_rate": round(over / n, 4) if n > 0 else 0.0,
        "emergency_total": em_total,
        "emergency_missed_count": em_miss,
        "emergency_missed": wilson_dict(em_miss, em_total),
        "emergency_to_routine_count": em_to_routine,
        "emergency_to_routine": wilson_dict(em_to_routine, em_total),
        "urgent_total": urg_total,
        "urgent_to_routine_count": urg_to_routine,
        "urgent_to_routine": wilson_dict(urg_to_routine, urg_total),
    }

    # Guardrail lift
    raw_em_tp = int((em_mask & (y_raw == 2)).sum())
    prod_em_tp = int((em_mask & (y_prod == 2)).sum())
    guardrail_lift = {
        "raw_emergency_sensitivity": wilson_dict(raw_em_tp, em_total),
        "production_emergency_sensitivity": wilson_dict(prod_em_tp, em_total),
        "guardrail_fire_rate": round(float(guardrail.mean()), 4) if n > 0 else 0.0,
        "guardrail_fired_count": int(guardrail.sum()),
    }

    # Calibration diagnostic
    correct = (y_prod == y_ref).astype(float)
    ece, bin_rows = expected_calibration_error(conf, correct)
    calibration_diagnostic = {
        "ece": round(ece, 4),
        "diagnostic_disclaimer": (
            "Limited predicted-class confidence diagnostic only; "
            "does not represent full clinical probability calibration."
        ),
        "bins": [
            {
                "bin_lower": round(lo, 2),
                "bin_upper": round(hi, 2),
                "count": m,
                "mean_confidence": round(avg_conf, 4),
                "accuracy": round(a, 4),
            }
            for lo, hi, m, avg_conf, a in bin_rows
        ],
    }

    # Subgroups (EMERGENCY sensitivity by age band, sex, vital completeness)
    ages = np.array([fd.get("patient_age", 0) or 0 for fd in formdatas])
    sexes = np.array([fd.get("patient_sex", "other") for fd in formdatas])
    incomplete = np.array([
        any(fd.get(k) is None for k in FIVE_VITAL_FIELDS)
        for fd in formdatas
    ])

    def _band(a):
        return (
            "<1" if a < 1 else "1-4" if a < 5 else "5-17" if a < 18
            else "18-64" if a < 65 else "65+"
        )

    band = np.array([_band(a) for a in ages])
    subgroups: Dict[str, Any] = {}

    subgroup_definitions = [
        ("age_under_1", band == "<1"),
        ("age_1_to_4", band == "1-4"),
        ("age_5_to_17", band == "5-17"),
        ("age_18_to_64", band == "18-64"),
        ("age_65_plus", band == "65+"),
        ("sex_male", sexes == "male"),
        ("sex_female", sexes == "female"),
        ("vitals_complete", ~incomplete),
        ("vitals_incomplete", incomplete),
    ]

    for sg_key, mask in subgroup_definitions:
        sub_em = mask & em_mask
        sub_em_count = int(sub_em.sum())
        sub_em_tp = int((sub_em & (y_prod == 2)).sum())
        subgroups[sg_key] = {
            "total_encounters": int(mask.sum()),
            "emergency_count": sub_em_count,
            "emergency_sensitivity": wilson_dict(sub_em_tp, sub_em_count),
        }

    return {
        "confusion_matrix": cm_list,
        "overall_agreement": round(acc, 4),
        "discrimination": discrimination,
        "safety_metrics": safety_metrics,
        "guardrail_lift": guardrail_lift,
        "calibration_diagnostic": calibration_diagnostic,
        "subgroups": subgroups,
    }


def _print_evaluation_report(
    manifest: SourceManifest,
    y_ref: np.ndarray,
    y_prod: np.ndarray,
    y_raw: np.ndarray,
    conf: np.ndarray,
    guardrail: np.ndarray,
    formdatas: List[Dict[str, Any]],
    metrics: Dict[str, Any],
) -> None:
    n = len(y_ref)
    print("=" * 74)
    print(f"EXTERNAL VALIDATION REPORT  —  {manifest.source_name}")
    print(
        f"n = {n}   reference mix: "
        + ", ".join(f"{TIER_NAME[t]}={int((y_ref == t).sum())}" for t in (0, 1, 2))
    )
    print("=" * 74)

    cm = metrics["confusion_matrix"]
    print("\nConfusion matrix (rows = reference, cols = VitalNet production):")
    print("               pred:ROUTINE  URGENT  EMERGENCY")
    for t in (0, 1, 2):
        print(f"  ref {TIER_NAME[t]:9} {cm[t][0]:9d} {cm[t][1]:8d} {cm[t][2]:10d}")

    print(f"\nOverall agreement with reference: {metrics['overall_agreement']:.4f}")

    print("\nPer-tier discrimination (one-vs-rest, Wilson 95% CI):")
    print(f"  {'tier':10} {'sensitivity':>22} {'specificity':>22} {'PPV':>22} {'NPV':>22}")
    for t in (0, 1, 2):
        t_name = TIER_NAME[t]
        d = metrics["discrimination"][t_name]
        print(
            f"  {t_name:10} {d['sensitivity']['formatted']:>22} "
            f"{d['specificity']['formatted']:>22} "
            f"{d['ppv']['formatted']:>22} {d['npv']['formatted']:>22}"
        )

    # ── SAFETY: under-triage relative to reference ───────────────────────────
    sm = metrics["safety_metrics"]
    print("\n*** SAFETY — under-triage (VitalNet shipped BELOW the reference) ***")
    print(
        f"  overall under-triage: {sm['overall_under_triage']['formatted']}   "
        f"(over-triage: {sm['overall_over_triage_rate']:.3f})"
    )
    print(
        f"  EMERGENCY missed (ref=EMERGENCY, pred<EMERGENCY): "
        f"{sm['emergency_missed']['formatted']}   "
        f"(of which two-tier ->ROUTINE: {sm['emergency_to_routine_count']})"
    )
    print(
        f"  URGENT ->ROUTINE (ref=URGENT, pred=ROUTINE):      "
        f"{sm['urgent_to_routine']['formatted']}"
    )

    # ── guardrail lift on real data ──────────────────────────────────────────
    gl = metrics["guardrail_lift"]
    print("\nDeterministic guardrail contribution (real-data lift):")
    print(f"  EMERGENCY sensitivity — raw model : {gl['raw_emergency_sensitivity']['formatted']}")
    print(f"  EMERGENCY sensitivity — production : {gl['production_emergency_sensitivity']['formatted']}")
    print(f"  cases where a guardrail fired      : {gl['guardrail_fire_rate']:.3f}")

    # ── calibration diagnostic ───────────────────────────────────────────────
    cd = metrics["calibration_diagnostic"]
    print(f"\nCalibration (predicted-class confidence vs correctness): ECE = {cd['ece']:.4f}")
    print(f"[{cd['diagnostic_disclaimer']}]")
    for b in cd["bins"]:
        print(
            f"    conf [{b['bin_lower']:.1f}-{b['bin_upper']:.1f}]  "
            f"n={b['count']:6d}  mean_conf={b['mean_confidence']:.3f}  accuracy={b['accuracy']:.3f}"
        )

    # ── subgroup: EMERGENCY sensitivity ─────────────────────────────────────
    print("\nSubgroup — EMERGENCY sensitivity (the equity/safety slice that matters):")
    sg = metrics["subgroups"]
    subgroup_labels = [
        ("age <1", "age_under_1"),
        ("age 1-4", "age_1_to_4"),
        ("age 5-17", "age_5_to_17"),
        ("age 18-64", "age_18_to_64"),
        ("age 65+", "age_65_plus"),
        ("sex male", "sex_male"),
        ("sex female", "sex_female"),
        ("vitals complete", "vitals_complete"),
        ("vitals incomplete", "vitals_incomplete"),
    ]
    for lbl, k in subgroup_labels:
        sub_info = sg.get(k, {})
        n_em = sub_info.get("emergency_count", 0)
        sens_fmt = sub_info.get("emergency_sensitivity", {}).get("formatted", "   n/a   ")
        print(f"  {lbl:18} n(EMERGENCY)={n_em:5d}   sensitivity={sens_fmt}")

    print("\n" + "=" * 74)
    print(
        "Report complete. Population-mismatch caveat applies — see "
        "docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md §7."
    )
    print("=" * 74)


def build_evaluation_json_report(
    manifest: SourceManifest,
    counters: ExclusionCounters,
    metrics: Dict[str, Any],
    formdatas: List[Dict[str, Any]],
) -> Dict[str, Any]:
    n_records = len(formdatas)
    vital_fields = list(FIVE_VITAL_FIELDS)
    present_counts = {vf: 0 for vf in vital_fields}
    vital_sums = {vf: 0.0 for vf in vital_fields}
    vital_mins = {vf: float("inf") for vf in vital_fields}
    vital_maxs = {vf: float("-inf") for vf in vital_fields}
    complete_count = 0

    for fd in formdatas:
        is_comp = True
        for vf in vital_fields:
            val = fd.get(vf)
            if val is not None:
                present_counts[vf] += 1
                vital_sums[vf] += float(val)
                if float(val) < vital_mins[vf]:
                    vital_mins[vf] = float(val)
                if float(val) > vital_maxs[vf]:
                    vital_maxs[vf] = float(val)
            else:
                is_comp = False
        if is_comp:
            complete_count += 1

    missingness_by_field: Dict[str, Dict[str, Any]] = {}
    vital_distributions: Dict[str, Dict[str, Any]] = {}
    for vf in vital_fields:
        pres = present_counts[vf]
        miss = n_records - pres
        pct = round((miss / n_records) * 100.0, 2) if n_records > 0 else 0.0
        missingness_by_field[vf] = {
            "missing_count": miss,
            "valid_count": pres,
            "missing_pct": pct,
            "valid_pct": round(100.0 - pct, 2),
        }
        if pres > 0:
            vital_distributions[vf] = {
                "valid_count": pres,
                "mean": round(vital_sums[vf] / pres, 2),
                "min": vital_mins[vf],
                "max": vital_maxs[vf],
                "missingness_pct": pct,
            }

    data_quality = {
        "field_missingness": missingness_by_field,
        "vital_ranges": vital_distributions,
        "complete_vitals_count": complete_count,
        "complete_vitals_pct": (
            round((complete_count / n_records) * 100.0, 2) if n_records > 0 else 0.0
        ),
    }

    return {
        "source_manifest": manifest.to_dict(),
        "evaluation_provenance": _get_evaluation_provenance(),
        "execution_mode": "evaluation",
        "cohort_flow": counters.to_dict(),
        "data_quality": data_quality,
        "metrics": metrics,
        "limitations_and_non_claims": LIMITATIONS_AND_NON_CLAIMS,
    }


def evaluate(
    formdatas: List[Dict[str, Any]],
    y_ref: np.ndarray,
    source_label: str,
    json_out: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible evaluation core entry point operating on formdatas and y_ref.
    """
    clf_mod.load_classifier()
    engineer = clf_mod._feature_engineer
    if engineer is None:
        from app.ml.clinical_features import ClinicalFeatureEngineer
        engineer = ClinicalFeatureEngineer()
        clf_mod._feature_engineer = engineer

    n = len(y_ref)
    y_prod = np.empty(n, dtype=int)
    y_raw = np.empty(n, dtype=int)
    conf = np.empty(n, dtype=float)
    guardrail = np.zeros(n, dtype=bool)

    for i, fd in enumerate(formdatas):
        res = clf_mod.predict_triage(fd)
        y_prod[i] = TIER_INDICES[res["triage_level"]]
        guardrail[i] = bool(res.get("safety_net_triggered") or res.get("news2_floor_triggered"))
        probs = res.get("probabilities")
        conf[i] = max(probs.values()) if probs else float(res.get("confidence_score", 1.0))
        # raw model tier (no guardrails) for the lift analysis
        fv = np.array(
            [[engineer.engineer_features(fd)[nm] for nm in clf_mod._feature_names]],
            dtype=np.float32,
        )
        y_raw[i] = int(np.argmax(clf_mod._classifier.predict_proba(fv)[0]))

    metrics = calculate_evaluation_metrics(
        y_ref=y_ref,
        y_prod=y_prod,
        y_raw=y_raw,
        conf=conf,
        guardrail=guardrail,
        formdatas=formdatas,
    )
    manifest = SourceManifest(
        source_id="generic",
        source_name=source_label,
        version="1.0",
        official_url="Generic / Self-Test",
        license_note="N/A",
    )
    _print_evaluation_report(manifest, y_ref, y_prod, y_raw, conf, guardrail, formdatas, metrics)
    if json_out:
        counters = ExclusionCounters(total_records=n, valid_records=n, excluded_records=0)
        report_dict = build_evaluation_json_report(manifest, counters, metrics, formdatas)
        assert_zero_patient_leakage(report_dict)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
        print(f"\nAggregate-only JSON evaluation report saved to: {json_out}")
    return metrics


def run_evaluation(
    source_id: str,
    file_path: Optional[str] = None,
    patients_file_path: Optional[str] = None,
    edstays_file_path: Optional[str] = None,
    medrecon_file_path: Optional[str] = None,
    cohort_policy: str = "all_stays",
    gate_m4_authorized: bool = False,
    input_mode: str = "mimic_triage_contract_v1",
    json_out: Optional[str] = None,
    acuity_scale: str = "esi",
    temp_fahrenheit: bool = False,
    n: int = 8000,
    seed: int = 2026,
) -> Dict[str, Any]:
    source = get_evaluation_source(
        source_id=source_id,
        file_path=file_path,
        patients_file_path=patients_file_path,
        edstays_file_path=edstays_file_path,
        medrecon_file_path=medrecon_file_path,
        cohort_policy=cohort_policy,
        gate_m4_authorized=gate_m4_authorized,
        input_mode=input_mode,
        acuity_scale=acuity_scale,
        temp_fahrenheit=temp_fahrenheit,
        n=n,
        seed=seed,
    )

    try:
        records, counters, manifest = source.load_for_evaluation(
            file_path=file_path,
            patients_file_path=patients_file_path,
            edstays_file_path=edstays_file_path,
            medrecon_file_path=medrecon_file_path,
        )
    except EvaluationRefusedError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.exit(2)

    if not records:
        print("[warn] No valid records loaded for evaluation.")
        return {}

    clf_mod.load_classifier()
    engineer = clf_mod._feature_engineer
    if engineer is None:
        from app.ml.clinical_features import ClinicalFeatureEngineer
        engineer = ClinicalFeatureEngineer()
        clf_mod._feature_engineer = engineer

    n_records = len(records)
    y_ref = np.empty(n_records, dtype=int)
    y_prod = np.empty(n_records, dtype=int)
    y_raw = np.empty(n_records, dtype=int)
    conf = np.empty(n_records, dtype=float)
    guardrail = np.zeros(n_records, dtype=bool)
    formdatas = []

    for i, rec in enumerate(records):
        fd = rec.form_data
        formdatas.append(fd)
        y_ref[i] = rec.reference_tier_index if rec.reference_tier_index is not None else 0

        res = clf_mod.predict_triage(fd)
        y_prod[i] = TIER_INDICES[res["triage_level"]]
        guardrail[i] = bool(res.get("safety_net_triggered") or res.get("news2_floor_triggered"))
        probs = res.get("probabilities")
        conf[i] = max(probs.values()) if probs else float(res.get("confidence_score", 1.0))

        # Raw model prediction without guardrails for lift calculation
        fv = np.array(
            [[engineer.engineer_features(fd)[nm] for nm in clf_mod._feature_names]],
            dtype=np.float32,
        )
        y_raw[i] = int(np.argmax(clf_mod._classifier.predict_proba(fv)[0]))

    metrics_dict = calculate_evaluation_metrics(
        y_ref=y_ref,
        y_prod=y_prod,
        y_raw=y_raw,
        conf=conf,
        guardrail=guardrail,
        formdatas=formdatas,
    )

    _print_evaluation_report(
        manifest=manifest,
        y_ref=y_ref,
        y_prod=y_prod,
        y_raw=y_raw,
        conf=conf,
        guardrail=guardrail,
        formdatas=formdatas,
        metrics=metrics_dict,
    )

    if json_out:
        report_dict = build_evaluation_json_report(
            manifest=manifest,
            counters=counters,
            metrics=metrics_dict,
            formdatas=formdatas,
        )
        assert_zero_patient_leakage(report_dict)
        out_dir = os.path.dirname(json_out)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
        print(f"\nAggregate-only JSON evaluation report saved to: {json_out}")

    return metrics_dict


# ── Main Entry Point ──────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="VitalNet External Validation and Inspection Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--inspect-source",
        choices=["iran-ed", "nhamcs-2022", "mimic-iv-ed", "iran_ed", "nhamcs_2022", "mimic_iv_ed", "generic-csv", "self-test"],
        help="Runs source inspection mode and outputs data quality metrics (e.g. iran-ed, nhamcs-2022, mimic-iv-ed).",
    )
    ap.add_argument(
        "--evaluate-source",
        choices=["iran-ed", "nhamcs-2022", "mimic-iv-ed", "generic-csv", "self-test", "iran_ed", "nhamcs_2022", "mimic_iv_ed"],
        help="Selects dataset adapter for evaluation (canonical alias for --dataset).",
    )
    ap.add_argument(
        "--dataset",
        choices=["iran-ed", "nhamcs-2022", "mimic-iv-ed", "generic-csv", "self-test", "iran_ed", "nhamcs_2022", "mimic_iv_ed"],
        help="Selects dataset adapter (alias for --evaluate-source).",
    )
    ap.add_argument(
        "--source",
        choices=["iran-ed", "nhamcs-2022", "mimic-iv-ed", "generic-csv", "self-test", "iran_ed", "nhamcs_2022", "mimic_iv_ed"],
        help="Selects dataset adapter (alias for --evaluate-source).",
    )
    ap.add_argument(
        "--file",
        help="Source data file path (CSV or fixed-width text).",
    )
    ap.add_argument(
        "--data-dir",
        help="Alias for --file (single file path).",
    )
    ap.add_argument(
        "--csv",
        help="Path to a labelled patient CSV (backward compatible alias for generic-csv --file).",
    )
    ap.add_argument(
        "--linkage-file",
        help="Optional linkage file path (e.g. ED_admission.csv for Iran ED).",
    )
    ap.add_argument(
        "--patients-file",
        "--patients",
        dest="patients_file",
        help="Path to MIMIC-IV patients.csv for anchor_age linkage.",
    )
    ap.add_argument(
        "--edstays-file",
        "--edstays",
        dest="edstays_file",
        help="Path to MIMIC-IV-ED edstays.csv for stay-level gender and encounter metadata.",
    )
    ap.add_argument(
        "--medrecon-file",
        "--medrecon",
        dest="medrecon_file",
        help="Path to MIMIC-IV-ED medrecon.csv (exploratory medication reconciliation).",
    )
    ap.add_argument(
        "--exploratory-medrecon-inspection",
        action="store_true",
        help="Explicitly enable exploratory inspection of medrecon file.",
    )
    ap.add_argument(
        "--cohort-policy",
        choices=["all_stays", "first_stay_only"],
        default="all_stays",
        help="Pre-registered cohort policy for repeated visits (default: all_stays).",
    )
    ap.add_argument(
        "--gate-m4-authorized",
        action="store_true",
        help="Explicit Gate M4 human authorization flag required to unlock frozen-model scoring on MIMIC-IV-ED.",
    )
    ap.add_argument(
        "--partial-input",
        action="store_true",
        help="Explicitly flag evaluation as partial-input mode.",
    )
    ap.add_argument(
        "--input-mode",
        choices=["full_input", "partial_input", "not_scored", "mimic_triage_contract_v1", "mimic_full_available_context_v1"],
        help="Evaluation input mode (full_input, partial_input, not_scored, mimic_triage_contract_v1, or mimic_full_available_context_v1).",
    )
    ap.add_argument(
        "--json-out",
        help="Output path for aggregate-only JSON report.",
    )
    ap.add_argument(
        "--report-json",
        help="Output path for aggregate-only JSON report (alias for --json-out).",
    )
    ap.add_argument(
        "--acuity-scale",
        choices=["esi", "ktas"],
        default="esi",
        help="How to map a 1-5 reference_acuity column to 3 tiers (default: esi).",
    )
    ap.add_argument(
        "--temp-fahrenheit",
        action="store_true",
        help="Convert a Fahrenheit temperature column to Celsius (e.g. MIMIC/NHAMCS).",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="Run the harness on synthetic data (machinery check only).",
    )
    ap.add_argument(
        "--n",
        type=int,
        default=8000,
        help="Number of synthetic encounters for self-test (default: 8000).",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Random seed for self-test (default: 2026).",
    )

    args = ap.parse_args()

    # Input mode validation
    source_id_to_check = args.evaluate_source or args.dataset or args.source
    if source_id_to_check:
        normalized_source = source_id_to_check.lower()
        if "nhamcs" in normalized_source:
            if args.input_mode is not None and args.input_mode != "partial_input":
                sys.stderr.write("Error: NHAMCS only supports --input-mode partial_input\n")
                sys.exit(1)
        if "iran" in normalized_source:
            if args.input_mode == "full_input":
                sys.stderr.write("Error: Iran dataset does not support full_input scoring\n")
                sys.exit(1)
        if "mimic" in normalized_source:
            if args.input_mode == "mimic_full_available_context_v1":
                sys.stderr.write(
                    "Error: mimic_full_available_context_v1 is hard-disabled pending independent "
                    "temporal-eligibility review and separate authorization.\n"
                )
                sys.exit(1)

    # Route execution mode
    json_output_path = args.json_out or args.report_json
    input_file_path = args.file or args.data_dir or args.csv

    if args.inspect_source:
        run_inspection(
            source_id=args.inspect_source,
            file_path=input_file_path,
            linkage_file_path=args.linkage_file,
            patients_file_path=args.patients_file,
            edstays_file_path=args.edstays_file,
            medrecon_file_path=args.medrecon_file,
            exploratory_medrecon_inspection=args.exploratory_medrecon_inspection,
            cohort_policy=args.cohort_policy,
            json_out=json_output_path,
            acuity_scale=args.acuity_scale,
            temp_fahrenheit=args.temp_fahrenheit,
        )
    elif args.self_test:
        run_evaluation(
            source_id="self-test",
            file_path=None,
            json_out=json_output_path,
            n=args.n,
            seed=args.seed,
        )
    elif args.evaluate_source or args.dataset or args.source:
        source_id = args.evaluate_source or args.dataset or args.source
        run_evaluation(
            source_id=source_id,
            file_path=input_file_path,
            patients_file_path=args.patients_file,
            edstays_file_path=args.edstays_file,
            medrecon_file_path=args.medrecon_file,
            cohort_policy=args.cohort_policy,
            gate_m4_authorized=args.gate_m4_authorized,
            input_mode=args.input_mode or "mimic_triage_contract_v1",
            json_out=json_output_path,
            acuity_scale=args.acuity_scale,
            temp_fahrenheit=args.temp_fahrenheit,
            n=args.n,
            seed=args.seed,
        )
    elif args.csv:
        run_evaluation(
            source_id="generic-csv",
            file_path=args.csv,
            json_out=json_output_path,
            acuity_scale=args.acuity_scale,
            temp_fahrenheit=args.temp_fahrenheit,
        )
    elif args.file or args.data_dir:
        run_evaluation(
            source_id="generic-csv",
            file_path=input_file_path,
            json_out=json_output_path,
            acuity_scale=args.acuity_scale,
            temp_fahrenheit=args.temp_fahrenheit,
        )
    else:
        ap.error("Must provide --inspect-source, --dataset/--source, --csv, or --self-test")



if __name__ == "__main__":
    main()
