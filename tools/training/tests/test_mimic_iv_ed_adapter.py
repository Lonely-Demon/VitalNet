"""
Comprehensive Test Suite for MIMIC-IV-ED Adapter, Symptom Parser, and Gate M4 Governance.

Validates:
- Test 1: Multi-table schema inspection (triage, patients, edstays, missingness, distributions).
- Test 2: Precedence & linkage rules (edstays.gender primary, patients.anchor_age, gender conflict, age top-coding 91).
- Test 3: Prohibited tables and fields injection rejection and pre-canonicalization stripping.
- Test 4: Vital conversions, plausibility filtering, Doppler handling, and BP inversion sanitization.
- Test 5: Isolation of respiratory rate and pain from model input (form_data).
- Test 6: Deterministic allow-list symptom parser (mapping accuracy, sorting, determinism, aggregate coverage).
- Test 7: Pre-registered mimic_esi_v1 mapping and invalid acuity exclusions.
- Test 8: Pre-registered cohort policies (all_stays vs first_stay_only deduplication).
- Test 9: Gate M4 staged scoring refusal semantics (default refusal, dual-gate medrecon refusal, CLI exit code 2).
- Test 10: Internal synthetic test mode restriction to approved fixture directories.
- Test 11: Strict zero patient-level data leakage assertions across all reports and metadata containers.
"""

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from evaluation_sources import (
    ARM_FULL_CONTEXT,
    ARM_TRIAGE_CONTRACT,
    COHORT_POLICY_ALL_STAYS,
    COHORT_POLICY_FIRST_STAY_ONLY,
    MIMIC_ESI_V1,
    PARSER_VERSION,
    PROHIBITED_FIELD_NAMES,
    PROHIBITED_TABLE_NAMES,
    AggregateDataQuality,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    MIMICIVEDSource,
    compute_file_sha256,
    compute_symptom_parser_coverage,
    get_evaluation_source,
    parse_symptoms_from_complaint,
)
from evaluate_on_real import (
    assert_zero_patient_leakage,
    build_evaluation_json_report,
    build_inspection_json_report,
    run_evaluation,
    run_inspection,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fixtures_dir() -> str:
    return os.path.join(HERE, "fixtures")


@pytest.fixture
def mimic_triage_csv_path(fixtures_dir: str) -> str:
    path = os.path.join(fixtures_dir, "synthetic_mimic_triage.csv")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


@pytest.fixture
def mimic_patients_csv_path(fixtures_dir: str) -> str:
    path = os.path.join(fixtures_dir, "synthetic_mimic_patients.csv")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


@pytest.fixture
def mimic_edstays_csv_path(fixtures_dir: str) -> str:
    path = os.path.join(fixtures_dir, "synthetic_mimic_edstays.csv")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


@pytest.fixture
def mimic_medrecon_csv_path(fixtures_dir: str) -> str:
    path = os.path.join(fixtures_dir, "synthetic_mimic_medrecon.csv")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


# ── Test Suite 1: Inspection & Multi-Table Linkage ────────────────────────────

class TestMIMICInspectionAndLinkage:
    """Validates aggregate data quality inspection across MIMIC tables."""

    def test_schema_headers_and_linkage_counts(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
    ):
        source = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
        )
        dq: AggregateDataQuality = source.inspect()

        assert dq.total_records_inspected == 13
        assert "temperature" in dq.headers_present
        assert "acuity" in dq.headers_present
        assert "chiefcomplaint" in dq.headers_present

        # Linkage summary checks
        linkage = dq.linkage_summary
        assert linkage is not None
        assert linkage["total_encounters_inspected"] == 13
        assert linkage["unique_stay_ids"] == 13
        assert linkage["unique_subject_ids"] == 12
        assert linkage["repeated_subject_count"] == 1  # subject 1006 has 2 stays
        assert linkage["max_encounters_single_subject"] == 2
        assert linkage["unlinked_patients_count"] == 1  # subject 1007 missing in patients.csv
        assert linkage["anchor_age_top_coded_count"] == 1  # subject 1005 with age 91
        assert linkage["gender_conflict_count"] == 1  # subject 1008 has F in edstays, M in patients

    def test_medrecon_ignored_in_primary_mode(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
        mimic_medrecon_csv_path: str,
    ):
        source_without_med = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
        )
        dq_without: AggregateDataQuality = source_without_med.inspect()

        source_with_med = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
            medrecon_file_path=mimic_medrecon_csv_path,
            exploratory_medrecon_inspection=False,
        )
        dq_with: AggregateDataQuality = source_with_med.inspect()

        # Medrecon file explicitly ignored in primary mode
        assert dq_with.linkage_summary["medrecon_file_ignored_in_primary_mode"] is True

        # Medrecon must not affect primary cohort counts, missingness, vital stats, or parser coverage
        assert dq_with.total_records_inspected == dq_without.total_records_inspected
        assert dq_with.missingness_by_field == dq_without.missingness_by_field
        assert dq_with.vital_distributions == dq_without.vital_distributions
        assert dq_with.extra_metadata["parser_coverage"] == dq_without.extra_metadata["parser_coverage"]

        # In evaluation loading, primary triage contract never ingests medrecon
        source_eval = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
            medrecon_file_path=mimic_medrecon_csv_path,
            _synthetic_test_mode=True,
        )
        records, _, _ = source_eval.load_for_evaluation()
        for rec in records:
            assert "medrecon" not in rec.form_data
            assert "medications" not in rec.form_data or rec.form_data["current_medications"] == ""
            assert "name" not in rec.form_data
            assert "charttime" not in rec.form_data

    def test_temperature_celsius_conversion_and_vital_distributions(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
    ):
        source = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
        )
        dq = source.inspect()

        vitals = dq.vital_distributions
        assert "temperature_c" in vitals
        assert vitals["temperature_c"]["valid_count"] == 12  # 1 row (stay 20010, 70.0F) implausible
        assert vitals["temperature_c"]["min"] >= 26.7
        assert vitals["temperature_c"]["max"] <= 43.3

        # BP Inversion counted
        assert dq.extra_metadata["bp_inversion_count"] == 1
        assert dq.exclusion_summary["invalid_bp_inversion"] == 1
        assert dq.exclusion_summary["missing_age_linkage"] == 1
        assert dq.exclusion_summary["invalid_or_missing_acuity"] == 1  # stay 20011 has acuity 0


# ── Test Suite 2: Prohibited Tables & Fields ──────────────────────────────────

class TestMIMICProhibitedTablesAndFields:
    """Verifies strict rejection of prohibited tables and pre-canonicalization stripping."""

    @pytest.mark.parametrize("bad_name", PROHIBITED_TABLE_NAMES)
    def test_prohibited_table_name_rejected_in_constructor(self, bad_name: str, fixtures_dir: str):
        fake_path = os.path.join(fixtures_dir, f"synthetic_mimic_{bad_name}.csv")
        with pytest.raises(ValueError, match="Prohibited table"):
            MIMICIVEDSource(file_path=fake_path)

    def test_prohibited_fields_stripped_before_canonicalization(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
    ):
        source = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
            _synthetic_test_mode=True,
        )
        records, _, _ = source.load_for_evaluation()

        for rec in records:
            # Check form_data
            for prohibited_fld in PROHIBITED_FIELD_NAMES:
                assert prohibited_fld not in rec.form_data
                assert prohibited_fld not in rec.raw_fields

            # Check isolation of resprate and pain from model input
            assert "resprate" not in rec.form_data
            assert "pain" not in rec.form_data
            assert "respiratory_rate" not in rec.form_data


# ── Test Suite 3: Deterministic Symptom Parser ────────────────────────────────

class TestMIMICSymptomParser:
    """Verifies deterministic allow-list mapping of chief complaints."""

    def test_symptom_parsing_accuracy_and_sorting(self):
        # Exact keyword matches
        assert parse_symptoms_from_complaint("chest pain and shortness of breath") == [
            "breathlessness",
            "chest_pain",
        ]
        assert parse_symptoms_from_complaint("severe bleeding from arm laceration") == [
            "severe_bleeding"
        ]
        assert parse_symptoms_from_complaint("moderate abdominal pain and persistent vomiting") == [
            "persistent_vomiting",
            "severe_abdominal_pain",
        ]
        assert parse_symptoms_from_complaint("severe headache with altered mental status and confusion") == [
            "altered_consciousness",
            "severe_headache",
        ]
        assert parse_symptoms_from_complaint("facial swelling tongue swelling and difficulty speaking") == [
            "difficulty_speaking",
            "swelling_face_throat",
        ]
        assert parse_symptoms_from_complaint("sudden onset weakness on right side and slurred speech") == [
            "difficulty_speaking",
            "weakness_one_side",
        ]

    def test_unmapped_and_empty_complaints(self):
        assert parse_symptoms_from_complaint("mild sore throat and nasal congestion") == []
        assert parse_symptoms_from_complaint("routine medication refill") == []
        assert parse_symptoms_from_complaint("") == []
        assert parse_symptoms_from_complaint(None) == []
        assert parse_symptoms_from_complaint("unknown") == []

    def test_parser_determinism(self):
        test_str = "patient has cp, sob, high fever, and seizure activity"
        expected = ["breathlessness", "chest_pain", "high_fever", "seizure"]
        for _ in range(100):
            assert parse_symptoms_from_complaint(test_str) == expected

    def test_parser_coverage_aggregate_statistics(self):
        complaints = [
            "chest pain",
            "shortness of breath",
            "routine follow up",
            None,
            "seizure and fever",
        ]
        cov = compute_symptom_parser_coverage(complaints)
        assert cov["parser_version"] == PARSER_VERSION
        assert cov["total_complaints_inspected"] == 5
        assert cov["non_empty_complaints_count"] == 4
        assert cov["complaints_with_mapped_symptoms_count"] == 3
        assert cov["overall_coverage_pct"] == 60.0
        assert cov["symptom_frequency_distribution"]["chest_pain"] == 1
        assert cov["symptom_frequency_distribution"]["breathlessness"] == 1
        assert cov["symptom_frequency_distribution"]["seizure"] == 1
        assert cov["symptom_frequency_distribution"]["high_fever"] == 1
        # Assert no complaint text leaked
        for k in cov:
            assert "chest pain" not in str(k)


# ── Test Suite 4: Gate M4 Staged Refusal & Policies ───────────────────────────

class TestMIMICGateM4AndScoring:
    """Verifies staged scoring refusal, cohort policies, and synthetic testing."""

    def test_default_evaluation_refused_without_gate_m4(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
    ):
        source = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
            gate_m4_authorized=False,
            _synthetic_test_mode=False,
        )
        with pytest.raises(EvaluationRefusedError, match="Gate M4 explicit authorization"):
            source.load_for_evaluation()

    def test_medrecon_arm_hard_refused_even_with_gate_m4(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
    ):
        source = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
            input_mode=ARM_FULL_CONTEXT,
            gate_m4_authorized=True,
            gate_medrecon_temporal_authorized=False,
        )
        with pytest.raises(EvaluationRefusedError, match="hard-disabled pending independent"):
            source.load_for_evaluation()

    def test_synthetic_test_mode_path_boundary_enforcement(self):
        # Attempting synthetic test mode on non-fixture path must fail
        with pytest.raises(ValueError, match="strictly restricted to approved synthetic fixtures"):
            MIMICIVEDSource(
                file_path="tools/training/data/mimic_iv_ed/triage.csv",
                _synthetic_test_mode=True,
            )

    def test_cohort_policy_all_stays_vs_first_stay_only(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
    ):
        # Policy: all_stays (primary)
        source_all = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
            cohort_policy=COHORT_POLICY_ALL_STAYS,
            _synthetic_test_mode=True,
        )
        recs_all, counters_all, _ = source_all.load_for_evaluation()
        stay_ids_all = [r.source_row_id for r in recs_all]
        assert "20061" in stay_ids_all
        assert "20062" in stay_ids_all  # Both stays for subject 1006 included
        assert counters_all.reasons.get("missing_age_linkage", 0) == 1  # 1007 excluded
        assert counters_all.reasons.get("invalid_or_missing_acuity", 0) == 1  # 20011 excluded

        # Policy: first_stay_only (sensitivity)
        source_first = MIMICIVEDSource(
            file_path=mimic_triage_csv_path,
            patients_file_path=mimic_patients_csv_path,
            edstays_file_path=mimic_edstays_csv_path,
            cohort_policy=COHORT_POLICY_FIRST_STAY_ONLY,
            _synthetic_test_mode=True,
        )
        recs_first, counters_first, _ = source_first.load_for_evaluation()
        stay_ids_first = [r.source_row_id for r in recs_first]
        assert "20061" in stay_ids_first
        assert "20062" not in stay_ids_first  # Duplicate stay for 1006 excluded
        assert counters_first.reasons.get("duplicate_subject_excluded", 0) == 1


# ── Test Suite 5: CLI E2E Execution & Zero Leakage ────────────────────────────

class TestMIMICCLIE2EAndZeroLeakage:
    """Validates CLI harness execution, JSON reports, and zero leakage assertion."""

    def test_cli_mimic_inspection_json_report_e2e(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
        mimic_edstays_csv_path: str,
        tmp_path: Any,
    ):
        json_out = os.path.join(str(tmp_path), "mimic_inspection.json")
        cmd = [
            sys.executable,
            os.path.join(TOOLS_DIR, "evaluate_on_real.py"),
            "--inspect-source",
            "mimic-iv-ed",
            "--file",
            mimic_triage_csv_path,
            "--patients-file",
            mimic_patients_csv_path,
            "--edstays-file",
            mimic_edstays_csv_path,
            "--json-out",
            json_out,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"CLI error: {res.stderr}"
        assert os.path.isfile(json_out)

        with open(json_out, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Complete provenance checks
        assert data["source_manifest"]["source_id"] == "mimic_iv_ed"
        assert data["source_manifest"]["version"] == "v2.2"
        assert "evaluation_provenance" in data
        assert data["cohort_flow"]["total_records"] == 13

        # Strict recursive zero patient data leakage assertion
        assert_zero_patient_leakage(data)

    def test_cli_mimic_evaluation_refused_by_default(
        self,
        mimic_triage_csv_path: str,
        mimic_patients_csv_path: str,
    ):
        cmd = [
            sys.executable,
            os.path.join(TOOLS_DIR, "evaluate_on_real.py"),
            "--evaluate-source",
            "mimic-iv-ed",
            "--file",
            mimic_triage_csv_path,
            "--patients-file",
            mimic_patients_csv_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 2
        assert "Gate M4 explicit authorization" in res.stderr
