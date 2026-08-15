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
