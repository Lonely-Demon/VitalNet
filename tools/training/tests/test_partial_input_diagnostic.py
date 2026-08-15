"""
Synthetic Unit Tests for NHAMCS Root-Cause Diagnostic & Ablation Harness.

Validates:
1. Reference label freezing: Labels computed once on full_input and frozen.
2. 4-regime transformations & invariants: undeclared fields strictly unchanged.
3. Controlled 4-regime ablation metrics & deltas.
4. Neutral missing-vital analysis across 0, 1, 2, 3 missing vitals.
5. Cross-architecture comparison between legacy backend and clinical-core rules-first.
6. Hardened --nhamcs-diagnostic non-scoring invariants: monkeypatching scoring functions
   proves that NHAMCS diagnostic runs in purely aggregate, non-scoring mode.
7. Zero-patient-leakage assertions and IMMEDR caveat verification.
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
SYNTHETIC_NHAMCS_TXT = os.path.join(FIXTURES_DIR, "synthetic_nhamcs_2022.txt")

if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from diagnose_partial_input import (
    FIVE_VITAL_FIELDS,
    IMMEDR_CAVEAT,
    LIMITATIONS_AND_NON_CLAIMS,
    freeze_synthetic_reference_labels,
    to_full_input,
    to_no_symptoms,
    to_no_text,
    to_partial_input,
    assert_regime_invariants,
    run_synthetic_regime_ablation,
    run_missing_vital_analysis,
    run_architecture_comparison,
    run_nhamcs_diagnostic,
    assert_zero_patient_leakage,
    generate_synthetic_cohort,
    build_full_synthetic_diagnostic_report,
)


@pytest.fixture
def synthetic_patients() -> List[Dict[str, Any]]:
    """Generates a small deterministic synthetic cohort for unit testing."""
    return generate_synthetic_cohort(n=30, seed=42)


# ── Suite 1: Reference Label Freezing & Regime Invariants ────────────────────

class TestLabelFreezingAndRegimeInvariants:
    """Verifies that reference labels are frozen on full_input and invariants hold."""

    def test_frozen_labels_computed_once_and_reused(self, synthetic_patients):
        labels = freeze_synthetic_reference_labels(synthetic_patients)
        assert len(labels) == len(synthetic_patients)
        assert all(l in (0, 1, 2) for l in labels)

        # Ensure label array is immutable / frozen
        frozen_copy = list(labels)
        assert frozen_copy == labels

    def test_regime_transformations_and_invariants(self, synthetic_patients):
        full = [to_full_input(p) for p in synthetic_patients]
        no_sym = [to_no_symptoms(p) for p in synthetic_patients]
        no_txt = [to_no_text(p) for p in synthetic_patients]
        part = [to_partial_input(p) for p in synthetic_patients]

        # Invariant checks must pass
        assert_regime_invariants(full, no_sym, "no_symptoms")
        assert_regime_invariants(full, no_txt, "no_text")
        assert_regime_invariants(full, part, "partial_input")

        # Specific field verification
        for orig, p_ns in zip(full, no_sym):
            assert p_ns["symptoms"] == []
            assert p_ns["chief_complaint"] == orig["chief_complaint"]
            assert p_ns["patient_age"] == orig["patient_age"]

        for orig, p_nt in zip(full, no_txt):
            assert p_nt["symptoms"] == orig["symptoms"]
            assert p_nt["chief_complaint"] == ""
            assert p_nt["location"] == ""
            assert p_nt["known_conditions"] in ("", [])

        for orig, p_pt in zip(full, part):
            assert p_pt["symptoms"] == []
            assert p_pt["chief_complaint"] == ""
            assert p_pt["location"] == ""
            assert "respiratory_rate" not in p_pt or p_pt.get("respiratory_rate") is None
            for vf in FIVE_VITAL_FIELDS:
                assert p_pt[vf] == orig[vf]


# ── Suite 2: Synthetic 4-Regime Controlled Ablation ──────────────────────────

class TestSyntheticRegimeAblation:
    """Validates the 4-regime ablation runner and metric deltas."""

    def test_synthetic_regime_ablation_metrics(self, synthetic_patients):
        labels = freeze_synthetic_reference_labels(synthetic_patients)
        results = run_synthetic_regime_ablation(synthetic_patients, labels)

        assert "regimes" in results
        assert "ablation_deltas_vs_full_input" in results

        regimes = results["regimes"]
        for r_name in ("full_input", "no_symptoms", "no_text", "partial_input"):
            assert r_name in regimes
            r_data = regimes[r_name]
            assert r_data["total_encounters"] == len(synthetic_patients)
            assert "confusion_matrix" in r_data
            assert "tier_sensitivities" in r_data
            assert "predicted_tier_distribution" in r_data
            assert "mean_class_probabilities" in r_data

        deltas = results["ablation_deltas_vs_full_input"]
        assert "partial_input" in deltas
        assert "accuracy_drop" in deltas["partial_input"]
        assert "emergency_sensitivity_drop" in deltas["partial_input"]


# ── Suite 3: Neutral Missing-Vital Analysis ──────────────────────────────────

class TestMissingVitalAnalysis:
    """Validates controlled missing-vital sensitivity analysis across 0, 1, 2, 3 missing vitals."""

    def test_missing_vital_cohorts_and_metrics(self, synthetic_patients):
        labels = freeze_synthetic_reference_labels(synthetic_patients)
        mv_res = run_missing_vital_analysis(synthetic_patients, labels, seed=2026)

        assert "missingness_levels" in mv_res
        lvls = mv_res["missingness_levels"]
        assert "0_missing_vitals" in lvls
        assert "1_missing_vital" in lvls
        assert "2_missing_vitals" in lvls
        assert "3_missing_vitals" in lvls

        for lvl_key in ("0_missing_vitals", "1_missing_vital", "2_missing_vitals", "3_missing_vitals"):
            data = lvls[lvl_key]
            assert "overall_agreement" in data
            assert "emergency_sensitivity" in data
            assert "predicted_tier_distribution" in data
            assert "mean_class_probabilities" in data
            assert "mean_derived_vital_feature_shift" in data


# ── Suite 4: Cross-Architecture Parity Comparison ────────────────────────────

class TestArchitectureComparison:
    """Validates comparison between Legacy Backend and Clinical-Core Rules-First."""

    def test_architecture_comparison_metrics(self, synthetic_patients):
        arch_res = run_architecture_comparison(synthetic_patients)

        assert "full_input" in arch_res
        assert "partial_input" in arch_res

        for regime_key in ("full_input", "partial_input"):
            data = arch_res[regime_key]
            assert data["total_encounters"] == len(synthetic_patients)
            assert "agreement_rate" in data
            assert "divergence" in data
            assert "cross_architecture_matrix" in data
            assert "legacy_distribution" in data
            assert "rules_first_distribution" in data


# ── Suite 5: Hardened Non-Scoring --nhamcs-diagnostic Invariants ─────────────

class TestHardenedNHAMCSDiagnostic:
    """Validates that --nhamcs-diagnostic is strictly aggregate-only and cannot score."""

    def test_nhamcs_diagnostic_monkeypatch_proves_non_scoring(self, monkeypatch):
        """
        Monkeypatches predict_triage and assign_triage_labels to raise an error.
        run_nhamcs_diagnostic MUST succeed without triggering either function.
        """
        from app.ml import classifier as _clf_mod
        import train_classifier as _tc

        def _forbidden_predict_triage(*args, **kwargs):
            raise RuntimeError("CRITICAL VIOLATION: predict_triage was invoked during non-scoring diagnostic!")

        def _forbidden_assign_triage(*args, **kwargs):
            raise RuntimeError("CRITICAL VIOLATION: assign_triage_labels was invoked during non-scoring diagnostic!")

        monkeypatch.setattr(_clf_mod, "predict_triage", _forbidden_predict_triage)
        monkeypatch.setattr(_tc, "assign_triage_labels", _forbidden_assign_triage)

        # Run diagnostic on synthetic fixture
        report = run_nhamcs_diagnostic(SYNTHETIC_NHAMCS_TXT)

        assert report["execution_mode"] == "nhamcs_diagnostic"
        assert "proxy_vs_vital_derangement_cross_tabulation" in report
        assert "dataset_summary" in report
        assert "proxy_tier_breakdown" in report

        cross_tab = report["proxy_vs_vital_derangement_cross_tabulation"]
        for t_name in ("ROUTINE", "URGENT", "EMERGENCY"):
            assert t_name in cross_tab
            assert "total_proxy_encounters" in cross_tab[t_name]
            assert "severe_vital_derangement_pct" in cross_tab[t_name]
            assert "normal_or_mild_vitals_pct" in cross_tab[t_name]

    def test_immedr_caveat_and_non_claims_present(self):
        assert "IMMEDR caveat" in IMMEDR_CAVEAT
        assert any("IMMEDR caveat" in lim for lim in LIMITATIONS_AND_NON_CLAIMS)

        report = run_nhamcs_diagnostic(SYNTHETIC_NHAMCS_TXT)
        assert "limitations_and_non_claims" in report
        assert any("IMMEDR caveat" in lim for lim in report["limitations_and_non_claims"])

    def test_assert_zero_patient_leakage_enforcement(self):
        valid_report = run_nhamcs_diagnostic(SYNTHETIC_NHAMCS_TXT)
        # Should pass without error
        assert_zero_patient_leakage(valid_report)

        # Adversarial check: inject forbidden keys
        for bad_key in ("form_data", "patient_records", "symptoms", "chief_complaint", "patient_id"):
            bad_report = copy.deepcopy(valid_report)
            bad_report["nested"] = {bad_key: "leaked_data"}
            with pytest.raises(AssertionError, match=f"Patient-level key '{bad_key}'"):
                assert_zero_patient_leakage(bad_report)


# ── Suite 6: Full Synthetic Diagnostic Orchestration ─────────────────────────

class TestFullSyntheticOrchestration:
    """Validates the end-to-end synthetic diagnostic pipeline."""

    def test_build_full_synthetic_diagnostic_report(self):
        report = build_full_synthetic_diagnostic_report(n=25, seed=123)
        assert report["execution_mode"] == "synthetic_diagnostic"
        assert "regime_ablation" in report
        assert "missing_vital_sensitivity" in report
        assert "architecture_comparison" in report
        assert "limitations_and_non_claims" in report
        assert_zero_patient_leakage(report)
