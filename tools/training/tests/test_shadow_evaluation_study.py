"""Synthetic invariants for the controlled shadow-evaluation fixture."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Mapping

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, "..", ".."))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import study_shadow_evaluation as shadow


def _assert_no_dict_inside_lists(value: Any) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _assert_no_dict_inside_lists(nested)
    elif isinstance(value, list):
        assert not any(isinstance(item, dict) for item in value), "patient-level object found in aggregate report"
        for nested in value:
            _assert_no_dict_inside_lists(nested)


def test_shadow_report_is_aggregate_only_and_zero_leakage():
    report = shadow.run_shadow_evaluation(n_encounters=80, seed=42)
    shadow.assert_zero_patient_leakage(report)
    _assert_no_dict_inside_lists(report)

    serialized = json.dumps(report, sort_keys=True)
    for forbidden_key in shadow.FORBIDDEN_REPORT_KEYS:
        assert f'"{forbidden_key}"' not in serialized
    assert report["protocol_metadata"]["patient_level_output"] is False
    assert report["protocol_metadata"]["execution_mode"] == "synthetic_only"


def test_shadow_report_is_reproducible_for_fixed_seed():
    first = shadow.run_shadow_evaluation(n_encounters=80, seed=123)
    second = shadow.run_shadow_evaluation(n_encounters=80, seed=123)
    assert first == second


def test_shadow_report_changes_with_seed_without_changing_contract():
    first = shadow.run_shadow_evaluation(n_encounters=80, seed=123)
    second = shadow.run_shadow_evaluation(n_encounters=80, seed=124)
    assert first["protocol_metadata"]["random_seed"] != second["protocol_metadata"]["random_seed"]
    assert first["protocol_metadata"]["patient_level_output"] is False
    assert second["protocol_metadata"]["patient_level_output"] is False


def test_shadow_specific_safety_metric_separation():
    report = shadow.run_shadow_evaluation(n_encounters=120, seed=42)
    candidate = report["arms"]["candidate_remediation_v1"]
    ordinary = candidate["ordinary_tier_performance"]
    routing = candidate["non_triage_routing"]
    safety = candidate["safety_behavior"]

    assert set(ordinary) >= {
        "tiered_case_count",
        "emergency_sensitivity",
        "emergency_miss_count",
        "confusion_matrix_3x3",
    }
    assert routing["denominator_identity_holds"] is True
    assert routing["total_reference_emergencies"] == (
        routing["tiered_reference_emergencies"] + routing["emergency_cases_escalated"]
    )
    assert candidate["operational_burden"]["synthetic_reviewer_queue_size"] == routing["indeterminate_count"]
    assert safety["no_fabricated_ordinary_tier_for_indeterminate"] is True
    assert 0.0 <= safety["emergency_retention_or_escalation_rate"] <= 1.0
    assert "INSUFFICIENT_INFORMATION_FOR_CDS" not in json.dumps(ordinary)


def test_shadow_preserves_four_state_input_contract():
    report = shadow.run_shadow_evaluation(n_encounters=240, seed=42)
    integrity = report["arms"]["candidate_remediation_v1"]["input_contract_integrity"]
    state_counts = integrity["symptom_screening_state_counts"]
    assert set(state_counts) == set(shadow.SYMPTOM_STATES)
    assert sum(state_counts.values()) == 240
    assert integrity["empty_symptoms_not_implicit_negative_count"] >= 0
    assert integrity["explicit_negative_without_declaration_count"] == 0


def test_shadow_runtime_guard_rejects_forbidden_paths_and_flags_unconditionally():
    forbidden_paths = [
        "tools/training/data/nonexistent.csv",
        "tools/training/data/ktas_2019_raw.xlsx",
        "tools/training/data/ed2022_records.txt",
        "tools/training/data/mimic_iv_ed_sample.json",
        "evaluation_sources/nhamcs_2022.py",
        "data/nhamcs/survey_2022.csv",
        "evaluation_sources/iran_ed.py",
        "--gate-3a-scoring-authorized",
        "--gate-m4-authorization",
        "evaluate_on_real.py",
    ]
    for forbidden in forbidden_paths:
        with pytest.raises(PermissionError):
            shadow.assert_shadow_runtime_isolated(paths=[forbidden])


def test_shadow_runtime_guard_is_active_in_child_process():
    script = (
        "import sys; sys.path.insert(0, %r); "
        "import study_shadow_evaluation as s; "
        "s.assert_shadow_runtime_isolated(paths=['tools/training/data/nonexistent.py'])"
    ) % TOOLS_DIR
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "PermissionError" in completed.stderr


def test_shadow_output_formatter_contains_aggregates_only():
    report = shadow.run_shadow_evaluation(n_encounters=30, seed=7)
    rendered = shadow.format_report(report)
    assert "SYNTHETIC FIXTURE" in rendered
    assert "patient-level" in rendered
    assert "ROUTINE" not in rendered or "Baseline" in rendered
    assert "chief_complaint" not in rendered
    assert "Emergency sensitivity" in rendered
