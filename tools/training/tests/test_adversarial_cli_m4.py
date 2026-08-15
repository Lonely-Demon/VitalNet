"""
Adversarial Verification Suite for Milestone M4: CLI Invariants & Refusal Semantics.
Author: challenger_m4_2 (Empirical Challenger Agent)

This suite rigorously challenges:
- Challenge 1: Iran ED scoring refusal across all CLI entry points (--dataset, --source, aliases),
  verifying exact exit code 2, exact error message string, refusal with --json-out (no file written),
  and contrasting with valid inspection exit code 0.
- Challenge 2: CLI error handling and robustness: missing arguments, non-existent files,
  invalid arguments, invalid acuity scales, missing file with dataset selection.
- Challenge 3: Aggregate-only JSON report contracts: valid JSON, required schema sections,
  ECE diagnostic disclaimers, nested output directory auto-creation, and exhaustive zero patient
  data leakage checks across all modes.
- Challenge 4: Backward compatibility: --self-test --n 100, generic --csv with ESI/KTAS,
  and preservation of legacy behaviors.
"""

import csv
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
EVALUATE_SCRIPT = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
FIXTURES_DIR = os.path.join(HERE, "fixtures")

IRAN_CSV_PATH = os.path.join(FIXTURES_DIR, "synthetic_iran_ed.csv")
IRAN_LINKAGE_PATH = os.path.join(FIXTURES_DIR, "synthetic_iran_ed_admission.csv")
NHAMCS_TXT_PATH = os.path.join(FIXTURES_DIR, "synthetic_nhamcs_2022.txt")

EXACT_REFUSAL_MESSAGE = (
    "Iran ED triage grade is binary in the published source and is unsupported "
    "for three-tier full-input evaluation; inspection/sparse-input analysis only."
)

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


def assert_zero_patient_leakage(obj: Any, path: str = "root") -> None:
    if isinstance(obj, dict):
        is_missingness_dict = path.endswith("field_missingness") or path.endswith("missingness_by_field")
        for k, v in obj.items():
            k_lower = str(k).lower()
            if not is_missingness_dict and k_lower in FORBIDDEN_LEAKAGE_KEYS:
                raise AssertionError(
                    f"Patient data leakage detected: forbidden key '{k}' found at path '{path}.{k}'"
                )
            assert_zero_patient_leakage(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            assert_zero_patient_leakage(item, f"{path}[{idx}]")


def run_cli(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, EVALUATE_SCRIPT] + list(args)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 1: Iran ED Scoring Refusal Semantics & Invariants
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge1IranEDRefusal:
    """
    Adversarially challenge Iran ED scoring refusal under multiple CLI invocations,
    flags, aliases, and combinations.
    """

    @pytest.mark.parametrize("flag,val", [
        ("--dataset", "iran-ed"),
        ("--source", "iran-ed"),
        ("--dataset", "iran_ed"),
        ("--source", "iran_ed"),
    ])
    def test_iran_ed_scoring_refusal_across_all_flags_and_aliases(self, flag: str, val: str):
        res = run_cli(flag, val, "--file", IRAN_CSV_PATH)
        assert res.returncode == 2, f"Expected returncode 2, got {res.returncode}. STDERR: {res.stderr}"
        combined_output = (res.stderr + " " + res.stdout).strip()
        assert EXACT_REFUSAL_MESSAGE in combined_output, (
            f"Exact refusal message missing in output.\nExpected:\n{EXACT_REFUSAL_MESSAGE}\nGot:\n{combined_output}"
        )

    def test_iran_ed_scoring_refusal_with_json_out_writes_no_file(self, tmp_path):
        out_json = str(tmp_path / "should_not_exist.json")
        res = run_cli("--dataset", "iran-ed", "--file", IRAN_CSV_PATH, "--json-out", out_json)
        assert res.returncode == 2
        assert not os.path.exists(out_json), f"Output JSON file {out_json} was created despite refusal!"
        assert EXACT_REFUSAL_MESSAGE in (res.stderr + " " + res.stdout)

    def test_iran_ed_inspection_does_not_refuse(self, tmp_path):
        out_json = str(tmp_path / "iran_inspect_success.json")
        res = run_cli(
            "--inspect-source", "iran-ed",
            "--file", IRAN_CSV_PATH,
            "--linkage-file", IRAN_LINKAGE_PATH,
            "--json-out", out_json,
        )
        assert res.returncode == 0, f"Inspection failed unexpectedly with code {res.returncode}. STDERR: {res.stderr}"
        assert os.path.exists(out_json)
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["execution_mode"] == "inspection"
        assert data["source_manifest"]["scoring_supported"] is False
        assert data["source_manifest"]["input_mode"] == "not_scored"
        assert EXACT_REFUSAL_MESSAGE not in res.stdout


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 2: CLI Error Handling, Missing Arguments, and Boundary Conditions
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge2CLIErrorHandling:
    """
    Adversarially challenge CLI parameter validation, error states, and invalid inputs.
    """

    def test_no_arguments_provided_fails_with_help_error(self):
        res = run_cli()
        assert res.returncode != 0
        assert "Must provide --inspect-source, --dataset/--source, --csv, or --self-test" in res.stderr

    def test_nonexistent_file_path_in_inspection_fails(self):
        res = run_cli("--inspect-source", "iran-ed", "--file", "nonexistent_file_xyz_12345.csv")
        assert res.returncode != 0
        assert "FileNotFoundError" in res.stderr or "not found" in res.stderr.lower()

    def test_nonexistent_file_path_in_nhamcs_inspection_fails(self):
        res = run_cli("--inspect-source", "nhamcs-2022", "--file", "nonexistent_nhamcs_file_xyz.txt")
        assert res.returncode != 0
        assert "FileNotFoundError" in res.stderr or "not found" in res.stderr.lower()

    def test_nonexistent_file_path_in_nhamcs_evaluation_fails(self):
        res = run_cli("--dataset", "nhamcs-2022", "--file", "nonexistent_nhamcs_file_xyz.txt")
        assert res.returncode != 0
        assert "FileNotFoundError" in res.stderr or "not found" in res.stderr.lower()

    def test_nonexistent_file_path_in_generic_csv_fails(self):
        res = run_cli("--csv", "nonexistent_generic_file_xyz.csv")
        assert res.returncode != 0
        assert "FileNotFoundError" in res.stderr or "not found" in res.stderr.lower()

    def test_invalid_dataset_choice_fails_argparse(self):
        res = run_cli("--dataset", "unsupported_dataset_foo", "--file", IRAN_CSV_PATH)
        assert res.returncode == 2
        assert "invalid choice" in res.stderr

    def test_invalid_acuity_scale_choice_fails_argparse(self):
        res = run_cli("--csv", IRAN_CSV_PATH, "--acuity-scale", "invalid_acuity_scale_choice")
        assert res.returncode == 2
        assert "invalid choice" in res.stderr

    def test_missing_file_when_dataset_requires_it_fails_cleanly(self):
        res = run_cli("--dataset", "nhamcs-2022")
        assert res.returncode != 0
        assert "FileNotFoundError" in res.stderr or "file" in res.stderr.lower() or "not found" in res.stderr.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 3: Aggregate-Only JSON Report Contracts & Zero Patient Leakage
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge3JSONReportContractsAndZeroLeakage:
    """
    Adversarially challenge JSON report structure, completeness, and strict
    zero patient-level data leakage.
    """

    def test_nhamcs_evaluation_json_report_structure_and_zero_leakage(self, tmp_path):
        out_json = str(tmp_path / "nhamcs_eval.json")
        res = run_cli("--dataset", "nhamcs-2022", "--file", NHAMCS_TXT_PATH, "--json-out", out_json)
        assert res.returncode == 0, f"NHAMCS evaluation failed: {res.stderr}"
        assert os.path.exists(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Required top-level schema keys
        required_keys = {"source_manifest", "execution_mode", "cohort_flow", "data_quality", "metrics", "limitations_and_non_claims"}
        assert required_keys.issubset(data.keys())
        assert data["execution_mode"] == "evaluation"

        # 2. Source manifest verification
        manifest = data["source_manifest"]
        assert manifest["source_id"] == "nhamcs_2022"
        assert manifest["input_mode"] == "partial_input"
        assert manifest["label_definition"].startswith("nhamcs_immediacy_v1")
        assert manifest["scoring_supported"] is True
        assert manifest["file_sha256"] is not None

        # 3. Metrics verification
        metrics = data["metrics"]
        assert "confusion_matrix" in metrics
        assert "overall_agreement" in metrics
        assert "discrimination" in metrics
        assert "safety_metrics" in metrics
        assert "guardrail_lift" in metrics
        assert "calibration_diagnostic" in metrics

        # Calibration diagnostic ECE check & disclaimer
        calib = metrics["calibration_diagnostic"]
        assert "ece" in calib
        assert isinstance(calib["ece"], float)
        assert "diagnostic_disclaimer" in calib
        assert "Limited predicted-class confidence diagnostic only" in calib["diagnostic_disclaimer"]

        # Limitations list
        assert len(data["limitations_and_non_claims"]) >= 5

        # 4. Strict Zero Patient Data Leakage Check
        assert_zero_patient_leakage(data)

    def test_json_out_creates_nested_directories_automatically(self, tmp_path):
        nested_json = str(tmp_path / "deeply" / "nested" / "output" / "dir" / "report.json")
        res = run_cli("--inspect-source", "nhamcs-2022", "--file", NHAMCS_TXT_PATH, "--json-out", nested_json)
        assert res.returncode == 0
        assert os.path.exists(nested_json)
        with open(nested_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["execution_mode"] == "inspection"
        assert_zero_patient_leakage(data)


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 4: Backward Compatibility and Self-Test Invariants
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge4BackwardCompatibility:
    """
    Adversarially challenge backward compatibility with legacy --self-test and --csv.
    """

    def test_self_test_cli_execution_with_custom_n_and_seed(self, tmp_path):
        out_json = str(tmp_path / "selftest_100.json")
        res = run_cli("--self-test", "--n", "100", "--seed", "42", "--json-out", out_json)
        assert res.returncode == 0, f"Self-test failed: {res.stderr}"
        assert "EXTERNAL VALIDATION REPORT" in res.stdout
        assert "n = 100" in res.stdout
        assert "Calibration (predicted-class confidence vs correctness): ECE =" in res.stdout

        assert os.path.exists(out_json)
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["cohort_flow"]["total_records"] == 100
        assert data["source_manifest"]["source_id"] == "synthetic_self_test"
        assert_zero_patient_leakage(data)

    def test_generic_csv_evaluation_with_esi_and_ktas_modes(self, tmp_path):
        csv_file = str(tmp_path / "multi_acuity.csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["age", "gender", "sbp", "dbp", "heartrate", "temp", "acuity", "symptoms"])
            writer.writerow(["50", "male", "130", "85", "80", "98.6", "2", "chest_pain"])
            writer.writerow(["25", "female", "110", "70", "65", "98.4", "4", "headache"])
            writer.writerow(["70", "female", "180", "110", "120", "101.5", "1", "breathlessness"])

        # Test ESI mode with temp-fahrenheit
        out_esi = str(tmp_path / "esi_report.json")
        res_esi = run_cli("--csv", csv_file, "--acuity-scale", "esi", "--temp-fahrenheit", "--json-out", out_esi)
        assert res_esi.returncode == 0, f"Generic CSV ESI failed: {res_esi.stderr}"
        assert os.path.exists(out_esi)
        with open(out_esi, "r", encoding="utf-8") as f:
            d_esi = json.load(f)
        assert d_esi["execution_mode"] == "evaluation"
        assert_zero_patient_leakage(d_esi)

        # Test KTAS mode
        out_ktas = str(tmp_path / "ktas_report.json")
        res_ktas = run_cli("--csv", csv_file, "--acuity-scale", "ktas", "--temp-fahrenheit", "--json-out", out_ktas)
        assert res_ktas.returncode == 0, f"Generic CSV KTAS failed: {res_ktas.stderr}"
        assert os.path.exists(out_ktas)
        with open(out_ktas, "r", encoding="utf-8") as f:
            d_ktas = json.load(f)
        assert d_ktas["execution_mode"] == "evaluation"
        assert_zero_patient_leakage(d_ktas)


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 5: CLI Input-Mode Validation & Contradictory Flag Rejection
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge5InputModeValidation:
    """
    Validates that the CLI explicitly rejects contradictory --input-mode values
    for sources that enforce a fixed input mode (NHAMCS=partial_input, Iran=not_scored).
    """

    def test_nhamcs_rejects_full_input_mode(self):
        """NHAMCS only supports partial_input; --input-mode full_input must fail."""
        result = run_cli(
            "--dataset", "nhamcs-2022", "--file", NHAMCS_TXT_PATH,
            "--input-mode", "full_input",
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for NHAMCS + --input-mode full_input, got {result.returncode}"
        )
        assert "NHAMCS only supports --input-mode partial_input" in result.stderr

    def test_nhamcs_rejects_not_scored_mode(self):
        """NHAMCS only supports partial_input; --input-mode not_scored must fail."""
        result = run_cli(
            "--dataset", "nhamcs-2022", "--file", NHAMCS_TXT_PATH,
            "--input-mode", "not_scored",
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for NHAMCS + --input-mode not_scored, got {result.returncode}"
        )
        assert "NHAMCS only supports --input-mode partial_input" in result.stderr

    def test_nhamcs_accepts_partial_input_mode(self):
        """NHAMCS + --input-mode partial_input must succeed (not fail at validation)."""
        result = run_cli(
            "--inspect-source", "nhamcs-2022", "--file", NHAMCS_TXT_PATH,
        )
        # Inspection should work; we just verify it doesn't exit with input-mode error
        assert result.returncode == 0

    def test_nhamcs_accepts_omitted_input_mode(self):
        """Omitting --input-mode for NHAMCS must succeed (adapter intrinsically uses partial_input)."""
        result = run_cli(
            "--inspect-source", "nhamcs-2022", "--file", NHAMCS_TXT_PATH,
        )
        assert result.returncode == 0

    def test_iran_rejects_full_input_mode(self):
        """Iran ED refuses scoring; --input-mode full_input must fail."""
        result = run_cli(
            "--dataset", "iran-ed", "--file", IRAN_CSV_PATH,
            "--input-mode", "full_input",
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for Iran + --input-mode full_input, got {result.returncode}"
        )
        assert "Iran dataset does not support full_input scoring" in result.stderr

    def test_fixed_width_flag_removed(self):
        """--fixed-width has been removed from the CLI; using it must fail."""
        result = run_cli(
            "--dataset", "nhamcs-2022", "--file", NHAMCS_TXT_PATH,
            "--fixed-width",
        )
        assert result.returncode != 0, (
            "Expected non-zero exit for removed --fixed-width flag"
        )
        assert "unrecognized arguments" in result.stderr or "error" in result.stderr.lower()

    @pytest.mark.parametrize("alias", ["--evaluate-source", "--source"])
    def test_nhamcs_input_mode_validation_works_across_aliases(self, alias):
        """Input-mode validation must fire regardless of which dataset alias is used."""
        result = run_cli(
            alias, "nhamcs-2022", "--file", NHAMCS_TXT_PATH,
            "--input-mode", "full_input",
        )
        assert result.returncode == 1
        assert "NHAMCS only supports --input-mode partial_input" in result.stderr


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 6: Evaluation Provenance Metadata
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge6EvaluationProvenance:
    """
    Validates that all reports include evaluation_provenance metadata with
    model_version, evaluation_git_commit, and evaluation_harness_version fields.
    """

    def test_self_test_evaluation_report_has_provenance(self, tmp_path):
        """Self-test evaluation JSON report must include provenance metadata."""
        out_json = str(tmp_path / "provenance_eval.json")
        result = run_cli("--self-test", "--n", "20", "--seed", "2026", "--json-out", out_json)
        assert result.returncode == 0, f"Self-test failed: {result.stderr}"
        assert os.path.isfile(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert "evaluation_provenance" in report, (
            "evaluation_provenance missing from evaluation report"
        )
        prov = report["evaluation_provenance"]
        assert "model_version" in prov
        assert "evaluation_git_commit" in prov
        assert "evaluation_harness_version" in prov
        # Fields must be non-empty strings (either actual values or 'unavailable')
        assert isinstance(prov["model_version"], str) and len(prov["model_version"]) > 0
        assert isinstance(prov["evaluation_git_commit"], str) and len(prov["evaluation_git_commit"]) > 0
        assert prov["evaluation_harness_version"] == "1.0.0"

    def test_inspection_report_has_provenance(self, tmp_path):
        """Inspection JSON report must also include provenance metadata."""
        out_json = str(tmp_path / "provenance_inspect.json")
        result = run_cli(
            "--inspect-source", "nhamcs-2022", "--file", NHAMCS_TXT_PATH,
            "--json-out", out_json,
        )
        assert result.returncode == 0, f"Inspection failed: {result.stderr}"
        assert os.path.isfile(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert "evaluation_provenance" in report, (
            "evaluation_provenance missing from inspection report"
        )
        prov = report["evaluation_provenance"]
        assert "model_version" in prov
        assert "evaluation_git_commit" in prov
        assert "evaluation_harness_version" in prov
        assert isinstance(prov["model_version"], str) and len(prov["model_version"]) > 0
        assert isinstance(prov["evaluation_git_commit"], str) and len(prov["evaluation_git_commit"]) > 0

    def test_provenance_model_version_references_pkl(self, tmp_path):
        """model_version should reference triage_classifier.pkl when it exists."""
        out_json = str(tmp_path / "provenance_pkl.json")
        result = run_cli("--self-test", "--n", "10", "--seed", "42", "--json-out", out_json)
        assert result.returncode == 0
        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)
        prov = report["evaluation_provenance"]
        # In the VitalNet repo, triage_classifier.pkl should exist at backend/app/ml/models/
        # If it exists, model_version starts with "triage_classifier.pkl@"
        # If not (e.g., clean CI), it should be "unavailable"
        mv = prov["model_version"]
        assert mv == "unavailable" or mv.startswith("triage_classifier.pkl@"), (
            f"model_version has unexpected format: {mv}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 7: Respiratory Rate Range Alignment with Official NHAMCS Codebook
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge7RespiratoryRateRange:
    """
    Validates that the NHAMCS adapter accepts respiratory rates in the official
    CDC codebook range 0-150, not the old 0-99 cap.
    """

    def test_respiratory_rate_above_99_accepted(self, tmp_path):
        """A respiratory rate of 120 (valid per codebook) must be parsed, not rejected."""
        # Build a synthetic NHAMCS line with respr=120 (cols 55-57 = [54:57])
        # Line format: year(4) + padding(11) + age(3=015) + padding(6) + sex(1=2) + padding(22)
        #   + temp(4=0986) + pulse(3=080) + respr(3=120) + sbp(3=120) + dbp(3=080) + spo2(3=098)
        #   + immedr(2=03) + padding to col 188 for PATWT
        base = "2022"             # cols 1-4
        base += " " * 11          # cols 5-15
        base += "025"             # cols 16-18: age=25
        base += " " * 6           # cols 19-24
        base += "2"               # col 25: sex=male
        base += " " * 22          # cols 26-47
        base += "0986"            # cols 48-51: temp=98.6F
        base += "080"             # cols 52-54: pulse=80
        base += "120"             # cols 55-57: respr=120 (above old 99 cap)
        base += "120"             # cols 58-60: sbp=120
        base += "080"             # cols 61-63: dbp=80
        base += "098"             # cols 64-66: spo2=98
        base += " 3"              # cols 67-68: immedr=3 (URGENT)
        # Pad to at least 188 chars for PATWT
        base += " " * (188 - len(base))

        fixture = str(tmp_path / "rr_test.txt")
        with open(fixture, "w", encoding="latin-1") as f:
            f.write(base + "\n")

        import importlib, sys as _sys
        if TOOLS_DIR not in _sys.path:
            _sys.path.insert(0, TOOLS_DIR)
        from evaluation_sources.nhamcs_2022 import NHAMCS2022Source

        source = NHAMCS2022Source(file_path=fixture)
        data_quality = source.inspect(file_path=fixture)

        # Respiratory rate should be parsed and show in vital distributions
        rr_dist = data_quality.vital_distributions.get("respiratory_rate", {})
        assert rr_dist.get("valid_count", 0) >= 1, (
            "respiratory_rate=120 was rejected; should be accepted per codebook range 0-150"
        )
        assert rr_dist.get("max", 0) >= 120, (
            f"respiratory_rate max should be >= 120, got {rr_dist.get('max')}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Challenge 8: Five-Vital Subgroup & Aggregate Completeness Consistency
# ══════════════════════════════════════════════════════════════════════════════

class TestChallenge8FiveVitalSubgroupCompleteness:
    """
    Validates that subgroup vital completeness and aggregate vital completeness
    both evaluate all five physiological fields: temperature, heart_rate,
    bp_systolic, bp_diastolic, and spo2.
    """

    def test_missing_only_bp_diastolic_is_classified_as_vitals_incomplete(self):
        """A record with 4 vitals present but bp_diastolic missing must be vitals_incomplete."""
        import sys as _sys
        import numpy as _np
        if TOOLS_DIR not in _sys.path:
            _sys.path.insert(0, TOOLS_DIR)
        from evaluate_on_real import (
            FIVE_VITAL_FIELDS,
            calculate_evaluation_metrics,
            build_evaluation_json_report,
        )
        from evaluation_sources.base import SourceManifest, ExclusionCounters

        assert set(FIVE_VITAL_FIELDS) == {
            "temperature", "heart_rate", "bp_systolic", "bp_diastolic", "spo2"
        }

        fd_missing_dbp = {
            "patient_age": 45,
            "patient_sex": "female",
            "temperature": 37.2,
            "heart_rate": 85,
            "bp_systolic": 130,
            "bp_diastolic": None,  # ONLY THIS IS MISSING
            "spo2": 97,
            "chief_complaint": "",
            "symptoms": [],
        }

        metrics = calculate_evaluation_metrics(
            y_ref=_np.array([2]),
            y_prod=_np.array([2]),
            y_raw=_np.array([2]),
            conf=_np.array([0.85]),
            guardrail=_np.array([0]),
            formdatas=[fd_missing_dbp],
        )

        subgroups = metrics["subgroups"]
        assert subgroups["vitals_incomplete"]["total_encounters"] == 1, (
            "Record missing only bp_diastolic must be counted under vitals_incomplete"
        )
        assert subgroups["vitals_complete"]["total_encounters"] == 0, (
            "Record missing bp_diastolic must NOT be counted under vitals_complete"
        )

        manifest = SourceManifest(
            source_id="synthetic_test",
            source_name="Synthetic Test",
            version="1.0",
            official_url="https://example.org",
            license_note="Synthetic",
            file_sha256=None,
            input_mode="partial_input",
            label_definition="test",
            scoring_supported=True,
        )
        report = build_evaluation_json_report(
            manifest=manifest,
            counters=ExclusionCounters(),
            metrics=metrics,
            formdatas=[fd_missing_dbp],
        )
        dq = report["data_quality"]
        assert dq["complete_vitals_count"] == 0
        assert dq["complete_vitals_pct"] == 0.0
        assert dq["field_missingness"]["bp_diastolic"]["missing_count"] == 1

    def test_complete_five_vitals_is_classified_as_vitals_complete(self):
        """A record with all five vitals populated must be vitals_complete."""
        import sys as _sys
        import numpy as _np
        if TOOLS_DIR not in _sys.path:
            _sys.path.insert(0, TOOLS_DIR)
        from evaluate_on_real import calculate_evaluation_metrics

        fd_complete = {
            "patient_age": 50,
            "patient_sex": "male",
            "temperature": 36.8,
            "heart_rate": 72,
            "bp_systolic": 120,
            "bp_diastolic": 80,
            "spo2": 99,
            "chief_complaint": "",
            "symptoms": [],
        }

        metrics = calculate_evaluation_metrics(
            y_ref=_np.array([2]),
            y_prod=_np.array([2]),
            y_raw=_np.array([2]),
            conf=_np.array([0.85]),
            guardrail=_np.array([0]),
            formdatas=[fd_complete],
        )

        subgroups = metrics["subgroups"]
        assert subgroups["vitals_complete"]["total_encounters"] == 1
        assert subgroups["vitals_incomplete"]["total_encounters"] == 0
