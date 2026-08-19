"""
VitalNet controlled shadow-evaluation synthetic harness.

This module is a research-only fixture for validating the accounting and safety
shape of a future silent/shadow study. It never connects to a site, reads a
real dataset, emits a patient-level row, or changes the production model.

The harness compares two hidden system arms against an independent synthetic
clinician-decision reference:

* frozen_baseline_v3.1.0: the unchanged production classifier;
* candidate_remediation_v1: the research-only missing-context and escalation
  policy from the synthetic safety-remediation study.

All reporting is aggregate-only. The synthetic cohort remains in memory only
for the duration of the run and is never serialized into the report.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from app.ml import classifier as clf_mod  # noqa: E402
from study_safety_remediation import (  # noqa: E402
    FIVE_VITAL_FIELDS,
    TIER_INDICES,
    assert_zero_patient_leakage,
    evaluate_candidate_policy,
    generate_synthetic_study_cohort,
    wilson_dict,
)

PROTOCOL_VERSION = "shadow-evaluation-v1.0.0"
MODEL_VERSION = "v3.1.0-frozen"
CANDIDATE_POLICY_VERSION = "candidate_remediation_v1"
ORDINARY_TIERS = ("ROUTINE", "URGENT", "EMERGENCY")
SYMPTOM_STATES: Tuple[str, ...] = (
    "positive_symptom",
    "explicit_negative_screen",
    "unknown_or_not_asked",
    "declined_or_unavailable",
)

FORBIDDEN_RUNTIME_TOKENS: Tuple[str, ...] = (
    "tools/training/data",
    "evaluation_sources",
    "ed2022",
    "ed_admission",
    "nhamcs",
    "iran_ed",
    "mimic_iv_ed",
    "ktas_2019",
    "--evaluate-source",
    "--gate-3a-scoring-authorized",
    "--gate-m4-authorization",
    "evaluate_on_real.py",
)
FORBIDDEN_REPORT_KEYS = {
    "records",
    "rows",
    "encounters",
    "patient_records",
    "patient_id",
    "mrn",
    "chief_complaint",
    "free_text",
    "symptoms",
    "observations",
    "current_medications",
    "known_conditions",
    "predictions",
    "prediction_list",
    "individual_probabilities",
}


def assert_shadow_runtime_isolated(
    argv: Sequence[str] | None = None,
    paths: Iterable[str] = (),
) -> None:
    """Fail closed if invocation or configured paths resemble real-data work."""
    values = [str(value).lower() for value in (argv or ())]
    values.extend(str(value).lower() for value in paths)
    for value in values:
        if any(token in value for token in FORBIDDEN_RUNTIME_TOKENS):
            raise PermissionError(
                "Shadow harness refuses real-data paths, adapters, or authorization flags: "
                f"{value}"
            )


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unavailable"


def _synthetic_clinician_reference(patient: Mapping[str, Any]) -> str:
    """Return an independent synthetic reference tier from latent severity.

    The latent severity is generated before any arm transformation and is not a
    production prediction. This deliberately simple reference is only a fixture
    for testing denominator integrity and report separation.
    """
    severity = str(patient.get("_research_underlying_severity", "moderate"))
    if severity in {"healthy", "mild"}:
        return "ROUTINE"
    if severity == "moderate":
        return "URGENT"
    return "EMERGENCY"


def _clean_production_input(patient: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in patient.items() if not str(key).startswith("_research_")}


def _model_output(patient: Mapping[str, Any]) -> Dict[str, Any]:
    if clf_mod._classifier is None:
        clf_mod.load_classifier()
    result = clf_mod.predict_triage(_clean_production_input(patient))
    tier = str(result["triage_level"])
    probabilities = result.get("probabilities") or {}
    ordered = [float(probabilities.get(tier_name, 0.0)) for tier_name in ORDINARY_TIERS]
    if sum(ordered) <= 0.0:
        ordered = [0.0, 0.0, 0.0]
        ordered[TIER_INDICES[tier]] = 1.0
    return {
        "tier": tier,
        "is_indeterminate": False,
        "reason_code": "standard_tiered",
        "extreme_vital_present": False,
        "probabilities": ordered,
    }


def _candidate_output(patient: Mapping[str, Any]) -> Dict[str, Any]:
    result = evaluate_candidate_policy(dict(patient))
    return {
        "tier": str(result["tier"]),
        "is_indeterminate": bool(result["is_indeterminate"]),
        "reason_code": str(result["reason_code"]),
        "extreme_vital_present": bool(result.get("extreme_vital_present", False)),
        "probabilities": [float(value) for value in result.get("probabilities", [0.0, 0.0, 0.0])],
    }


def _ordinary_metrics(reference: Sequence[str], outputs: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    tiered = [index for index, output in enumerate(outputs) if not output["is_indeterminate"]]
    matrix = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    under = 0
    over = 0
    emergency_hits = 0
    tiered_emergencies = 0
    two_tier_drops = 0
    for index in tiered:
        true_index = TIER_INDICES[reference[index]]
        predicted_index = TIER_INDICES[str(outputs[index]["tier"])]
        matrix[true_index][predicted_index] += 1
        if predicted_index < true_index:
            under += 1
            if true_index == 2 and predicted_index == 0:
                two_tier_drops += 1
        elif predicted_index > true_index:
            over += 1
        if true_index == 2:
            tiered_emergencies += 1
            if predicted_index == 2:
                emergency_hits += 1
    return {
        "tiered_case_count": len(tiered),
        "reference_emergencies_in_tiered_cases": tiered_emergencies,
        "emergency_sensitivity": wilson_dict(emergency_hits, tiered_emergencies),
        "emergency_miss_count": tiered_emergencies - emergency_hits,
        "emergency_miss_rate": round((tiered_emergencies - emergency_hits) / tiered_emergencies, 4) if tiered_emergencies else 0.0,
        "emergency_to_routine_drop_count": two_tier_drops,
        "emergency_to_routine_drop_rate": round(two_tier_drops / tiered_emergencies, 4) if tiered_emergencies else 0.0,
        "under_triage_count": under,
        "under_triage_rate": round(under / len(tiered), 4) if tiered else 0.0,
        "over_triage_count": over,
        "over_triage_rate": round(over / len(tiered), 4) if tiered else 0.0,
        "confusion_matrix_3x3": matrix,
    }


def _missing_vital_stratum(patient: Mapping[str, Any]) -> str:
    missing = sum(1 for field in FIVE_VITAL_FIELDS if patient.get(field) is None)
    if missing == 0:
        return "0_missing_vitals"
    if missing == 1:
        return "1_missing_vital"
    if missing == 2:
        return "2_missing_vitals"
    return "3_plus_missing_vitals"


def _aggregate_strata(
    cohort: Sequence[Mapping[str, Any]],
    reference: Sequence[str],
    outputs: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    strata: Dict[str, List[int]] = {
        "symptom_screening_states": [],
        "vital_missingness": [],
    }
    result: Dict[str, Any] = {"symptom_screening_states": {}, "vital_missingness": {}}
    for dimension, labels in (
        ("symptom_screening_states", [str(p.get("_research_symptom_screening_status")) for p in cohort]),
        ("vital_missingness", [_missing_vital_stratum(p) for p in cohort]),
    ):
        unique = sorted(set(labels))
        for label in unique:
            indices = [i for i, value in enumerate(labels) if value == label]
            subset_reference = [reference[i] for i in indices]
            subset_outputs = [outputs[i] for i in indices]
            ordinary = _ordinary_metrics(subset_reference, subset_outputs)
            result[dimension][label] = {
                "count": len(indices),
                "tiered_count": ordinary["tiered_case_count"],
                "indeterminate_count": len(indices) - ordinary["tiered_case_count"],
                "emergency_sensitivity": ordinary["emergency_sensitivity"]["point_estimate"],
                "under_triage_rate": ordinary["under_triage_rate"],
            }
    return result


def _aggregate_arm(
    arm_name: str,
    cohort: Sequence[Mapping[str, Any]],
    reference: Sequence[str],
    outputs: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    total = len(cohort)
    indeterminate = [i for i, output in enumerate(outputs) if output["is_indeterminate"]]
    reference_distribution = Counter(reference)
    escalated_distribution = Counter(reference[i] for i in indeterminate)
    reason_counts = Counter(str(output["reason_code"]) for output in outputs if output["is_indeterminate"])
    emergencies = sum(1 for tier in reference if tier == "EMERGENCY")
    emergency_escalated = sum(1 for i in indeterminate if reference[i] == "EMERGENCY")
    ordinary = _ordinary_metrics(reference, outputs)
    extreme_escalated = sum(
        1 for i in indeterminate if bool(outputs[i].get("extreme_vital_present", False))
    )
    extreme_observed = sum(
        1 for patient in cohort
        if (
            (patient.get("spo2") is not None and patient.get("spo2") <= 85)
            or (patient.get("heart_rate") is not None and (patient.get("heart_rate") < 35 or patient.get("heart_rate") > 170))
            or (patient.get("bp_systolic") is not None and (patient.get("bp_systolic") < 70 or patient.get("bp_systolic") > 220))
            or (patient.get("temperature") is not None and (patient.get("temperature") < 33.0 or patient.get("temperature") > 41.5))
        )
    )
    tiered_emergency_hits = ordinary["emergency_sensitivity"]["numerator"]
    return {
        "arm_name": arm_name,
        "cohort_size": total,
        "ordinary_tier_performance": ordinary,
        "non_triage_routing": {
            "indeterminate_count": len(indeterminate),
            "indeterminate_rate": round(len(indeterminate) / total, 4) if total else 0.0,
            "escalation_reason_counts": dict(sorted(reason_counts.items())),
            "reference_tier_distribution_among_escalated": {
                tier: int(escalated_distribution.get(tier, 0)) for tier in ORDINARY_TIERS
            },
            "total_reference_emergencies": emergencies,
            "tiered_reference_emergencies": ordinary["reference_emergencies_in_tiered_cases"],
            "emergency_cases_escalated": emergency_escalated,
            "denominator_identity_holds": emergencies == ordinary["reference_emergencies_in_tiered_cases"] + emergency_escalated,
        },
        "operational_burden": {
            "escalations_per_100_encounters": round((len(indeterminate) / total) * 100, 4) if total else 0.0,
            "synthetic_reviewer_queue_size": len(indeterminate),
            "synthetic_manual_review_required_rate": round(len(indeterminate) / total, 4) if total else 0.0,
            "synthetic_queue_age_seconds": 0,
            "note": "Synthetic workload proxies only; no clinical acceptance threshold is assigned.",
        },
        "input_contract_integrity": {
            "symptom_screening_state_counts": {
                state: sum(1 for patient in cohort if patient.get("_research_symptom_screening_status") == state)
                for state in SYMPTOM_STATES
            },
            "empty_symptoms_not_implicit_negative_count": sum(
                1 for patient in cohort
                if not patient.get("symptoms") and patient.get("_research_symptom_screening_status") != "explicit_negative_screen"
            ),
            "explicit_negative_without_declaration_count": sum(
                1 for patient in cohort
                if patient.get("_research_symptom_screening_status") == "explicit_negative_screen"
                and not bool(patient.get("_research_no_acute_danger_signs_declared"))
            ),
            "missing_vital_count_distribution": {
                label: sum(1 for patient in cohort if _missing_vital_stratum(patient) == label)
                for label in ("0_missing_vitals", "1_missing_vital", "2_missing_vitals", "3_plus_missing_vitals")
            },
            "provenance_completeness_rate": 1.0,
        },
        "safety_behavior": {
            "extreme_vitals_observed": extreme_observed,
            "extreme_vitals_flagged_during_escalation": extreme_escalated,
            "extreme_vital_preservation_rate": round(extreme_escalated / extreme_observed, 4) if extreme_observed else 1.0,
            "no_fabricated_ordinary_tier_for_indeterminate": all(
                output["is_indeterminate"] or output["tier"] in ORDINARY_TIERS for output in outputs
            ),
            "emergency_retention_or_escalation_rate": round(
                (tiered_emergency_hits + emergency_escalated) / emergencies, 4
            ) if emergencies else 0.0,
        },
        "stratified_metrics": _aggregate_strata(cohort, reference, outputs),
        "reference_tier_distribution": {tier: int(reference_distribution.get(tier, 0)) for tier in ORDINARY_TIERS},
    }


def run_shadow_evaluation(n_encounters: int = 1000, seed: int = 42) -> Dict[str, Any]:
    """Run the synthetic shadow comparison and return aggregate-only output."""
    if n_encounters <= 0 or n_encounters > 10000:
        raise ValueError("n_encounters must be between 1 and 10000")
    assert_shadow_runtime_isolated()
    cohort = generate_synthetic_study_cohort(n=n_encounters, seed=seed)
    reference = [_synthetic_clinician_reference(patient) for patient in cohort]
    baseline_outputs = [_model_output(patient) for patient in cohort]
    candidate_outputs = [_candidate_output(patient) for patient in cohort]
    report: Dict[str, Any] = {
        "protocol_metadata": {
            "protocol_version": PROTOCOL_VERSION,
            "study_name": "VitalNet Controlled Shadow-Evaluation Synthetic Fixture",
            "execution_mode": "synthetic_only",
            "model_version": MODEL_VERSION,
            "candidate_policy_version": CANDIDATE_POLICY_VERSION,
            "source_code_commit": _git_commit(),
            "random_seed": int(seed),
            "cohort_size": int(n_encounters),
            "reference_type": "independent_synthetic_clinician_decision_fixture",
            "patient_level_output": False,
        },
        "arms": {
            "frozen_baseline_v3.1.0": _aggregate_arm("frozen_baseline_v3.1.0", cohort, reference, baseline_outputs),
            "candidate_remediation_v1": _aggregate_arm("candidate_remediation_v1", cohort, reference, candidate_outputs),
        },
        "shadow_comparison": {
            "same_synthetic_cohort_for_all_arms": True,
            "reference_computed_independently_of_system_outputs": True,
            "system_output_hidden_from_reference_fixture": True,
            "ordinary_tier_metrics_separated_from_non_triage_states": True,
        },
        "non_claims": [
            "Synthetic fixture only; not clinical validation or clinical efficacy evidence.",
            "The synthetic clinician-decision reference is not a real clinician, outcome, or validated instrument.",
            "The candidate policy is research-only and is not active in the production runtime.",
            "No result supports autonomous triage, rural equivalence, ASHA equivalence, or regulatory clearance.",
        ],
    }
    assert_zero_patient_leakage(report)
    return report


def format_report(report: Mapping[str, Any]) -> str:
    """Render aggregate-only terminal output without patient-level detail."""
    baseline = report["arms"]["frozen_baseline_v3.1.0"]
    candidate = report["arms"]["candidate_remediation_v1"]
    lines = [
        "VITALNET CONTROLLED SHADOW-EVALUATION SYNTHETIC FIXTURE",
        f"Protocol: {report['protocol_metadata']['protocol_version']} | Cohort: {report['protocol_metadata']['cohort_size']} | Seed: {report['protocol_metadata']['random_seed']}",
        "",
        "Metric                                      Baseline       Candidate",
        "-" * 74,
        f"Emergency sensitivity (ordinary tier)      {baseline['ordinary_tier_performance']['emergency_sensitivity']['point_estimate']:.4f}       {candidate['ordinary_tier_performance']['emergency_sensitivity']['point_estimate']:.4f}",
        f"Emergency miss count (ordinary tier)       {baseline['ordinary_tier_performance']['emergency_miss_count']:>6}       {candidate['ordinary_tier_performance']['emergency_miss_count']:>6}",
        f"Indeterminate rate                          {baseline['non_triage_routing']['indeterminate_rate']:.4f}       {candidate['non_triage_routing']['indeterminate_rate']:.4f}",
        f"Emergency retention/escalation              {baseline['safety_behavior']['emergency_retention_or_escalation_rate']:.4f}       {candidate['safety_behavior']['emergency_retention_or_escalation_rate']:.4f}",
        "",
        "Synthetic-only output; no patient-level rows or clinical claims.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the synthetic-only VitalNet shadow-evaluation fixture.")
    parser.add_argument("--n-encounters", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args(argv)
    assert_shadow_runtime_isolated(argv or sys.argv[1:], [args.output])
    report = run_shadow_evaluation(n_encounters=args.n_encounters, seed=args.seed)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
