"""
VitalNet Comprehensive Evaluation Sources Test Suite.

Validates:
- Test 1: Iran ED inspection (published headers, missingness, triage distribution, binary urgency, completeness, linkage).
- Test 2: Iran ED scoring refusal (EvaluationRefusedError, CLI exit code 2, exact refusal message).
- Test 3: CDC NHAMCS 2022 fixed-width parsing (character offsets, cohort flow, short-line rejection).
- Test 4: CDC NHAMCS 2022 numerical & categorical conversions (Fahrenheit to Celsius, sex mapping, Doppler rejection, IMMEDR sentinels, BP ranges & physiological inversion).
- Test 5: CDC NHAMCS 2022 proxy mapping & partial-input enforcement (nhamcs_immediacy_v1, empty complaint/symptoms, model execution).
- Test 6: CDC NHAMCS 2022 unweighted metrics (PATWT stored in metadata only, unweighted Wilson proportions).
- Test 7: Aggregate-only JSON report contract (manifest, SHA-256, metrics, ECE disclaimer, strict zero-leakage).
- Test 8: Generic CSV and self-test backward compatibility (ESI/KTAS mapping, symptom allowlist, self-test harness).
"""

import csv
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pytest

# Ensure repo and tools paths are available
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from evaluation_sources import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    ExclusionCounters,
    GenericCSVSource,
    IranEDSource,
    NHAMCS2022Source,
    NHAMCS_IMMEDIACY_V1,
    PUBLISHED_HEADERS,
    EXACT_REFUSAL_MESSAGE,
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
from evaluate_on_real import (
    assert_zero_patient_leakage,
    build_evaluation_json_report,
    build_inspection_json_report,
    calculate_evaluation_metrics,
    expected_calibration_error,
    run_evaluation,
    run_inspection,
    wilson,
    wilson_dict,
)

from app.ml import classifier as clf_mod


# ── Fixture Paths ────────────────────────────────────────────────────────────

@pytest.fixture
def fixtures_dir() -> str:
    return os.path.join(HERE, "fixtures")


@pytest.fixture
def iran_ed_csv_path(fixtures_dir: str) -> str:
    path = os.path.join(fixtures_dir, "synthetic_iran_ed.csv")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


@pytest.fixture
def iran_ed_admission_path(fixtures_dir: str) -> str:
    path = os.path.join(fixtures_dir, "synthetic_iran_ed_admission.csv")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


@pytest.fixture
def nhamcs_2022_txt_path(fixtures_dir: str) -> str:
    path = os.path.join(fixtures_dir, "synthetic_nhamcs_2022.txt")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


# ── Test Suite 1: Iran ED Inspection ─────────────────────────────────────────

class TestIranEDInspection:
    """
    Test 1: Validates published headers extraction, row counts, missingness rates,
    triage grade distribution, binary urgency breakdown (Grades 1-2 vs 3-5),
    5-vital completeness, and admission linkage.
    """

    def test_iran_ed_published_headers_extraction(self, iran_ed_csv_path: str):
        source = IranEDSource(file_path=iran_ed_csv_path)
        dq: AggregateDataQuality = source.inspect()

        assert dq.headers_present == PUBLISHED_HEADERS
        assert len(dq.headers_present) == 10
        for expected_hdr in [
            "BlooddpressurSystol",
            "BlooddpressurDiastol",
            "PulseRate",
            "Temperature",
            "O2Saturation",
            "ChiefComplaint",
            "TriageGrade",
            "CriticalStatus",
            "NeedFastExecute",
            "triage_code",
        ]:
            assert expected_hdr in dq.headers_present

    def test_iran_ed_row_counts_and_missingness_rates(self, iran_ed_csv_path: str):
        source = IranEDSource(file_path=iran_ed_csv_path)
        dq: AggregateDataQuality = source.inspect()

        assert dq.total_records_inspected == 12

        # Missingness by field
        m_map = dq.missingness_by_field
        assert "BlooddpressurSystol" in m_map
        assert m_map["BlooddpressurSystol"]["missing_count"] == 1
        assert m_map["BlooddpressurSystol"]["valid_count"] == 11
        assert round(m_map["BlooddpressurSystol"]["missing_pct"], 2) == 8.33

        assert m_map["BlooddpressurDiastol"]["missing_count"] == 1
        assert m_map["PulseRate"]["missing_count"] == 1
        assert m_map["Temperature"]["missing_count"] == 1
        assert m_map["O2Saturation"]["missing_count"] == 1

        assert m_map["ChiefComplaint"]["missing_count"] == 0
        assert m_map["ChiefComplaint"]["valid_count"] == 12
        assert m_map["ChiefComplaint"]["missing_pct"] == 0.0

        assert m_map["TriageGrade"]["missing_count"] == 0
        assert m_map["TriageGrade"]["valid_count"] == 12

        assert m_map["CriticalStatus"]["missing_count"] == 1
        assert m_map["NeedFastExecute"]["missing_count"] == 1

    def test_iran_ed_triage_grade_and_binary_urgency_breakdown(self, iran_ed_csv_path: str):
        source = IranEDSource(file_path=iran_ed_csv_path)
        dq: AggregateDataQuality = source.inspect()

        # Triage grade distribution: 1:3, 2:2, 3:3, 4:2, 5:2
        assert dq.reference_distribution["1"] == 3
        assert dq.reference_distribution["2"] == 2
        assert dq.reference_distribution["3"] == 3
        assert dq.reference_distribution["4"] == 2
        assert dq.reference_distribution["5"] == 2
        assert dq.reference_distribution["other"] == 0

        # Binary urgency breakdown: Grades 1-2 (urgent) vs Grades 3-5 (non-urgent)
        binary_urgency = dq.extra_metadata["binary_urgency_distribution"]
        assert binary_urgency["urgent_grades_1_2"] == 5  # 3 (Grade 1) + 2 (Grade 2)
        assert binary_urgency["non_urgent_grades_3_5"] == 7  # 3 (Grade 3) + 2 (Grade 4) + 2 (Grade 5)
        assert binary_urgency["unclassified"] == 0

    def test_iran_ed_5_vital_completeness(self, iran_ed_csv_path: str):
        source = IranEDSource(file_path=iran_ed_csv_path)
        dq: AggregateDataQuality = source.inspect()

        # 8 out of 12 rows have complete 5 vitals
        assert dq.complete_vitals_count == 8
        assert round(dq.complete_vitals_pct, 2) == 66.67

        # Vital distributions contain mean, min, max, missingness
        v_dist = dq.vital_distributions
        assert "BlooddpressurSystol" in v_dist
        assert v_dist["BlooddpressurSystol"]["valid_count"] == 11
        assert v_dist["BlooddpressurSystol"]["min"] == 105.0
        assert v_dist["BlooddpressurSystol"]["max"] == 160.0
        assert v_dist["BlooddpressurSystol"]["mean"] > 0

    def test_iran_ed_admission_linkage(self, iran_ed_csv_path: str, iran_ed_admission_path: str):
        source = IranEDSource(file_path=iran_ed_csv_path, linkage_file_path=iran_ed_admission_path)
        dq: AggregateDataQuality = source.inspect()

        assert dq.linkage_summary is not None
        assert dq.linkage_summary["status"] == "linked"
        assert dq.linkage_summary["total_admission_records"] == 8
        assert dq.linkage_summary["unique_admission_keys"] == 8
        assert dq.linkage_summary["unique_primary_keys"] == 12
        assert dq.linkage_summary["matched_encounter_keys"] == 6
        assert dq.linkage_summary["encounter_match_rate_pct"] == 50.0
        assert dq.linkage_summary["linkage_sha256"] == compute_file_sha256(iran_ed_admission_path)

    def test_iran_ed_missing_file_raises_error(self):
        source = IranEDSource(file_path="non_existent_file.csv")
        with pytest.raises(FileNotFoundError):
            source.inspect()


# ── Test Suite 2: Iran ED Scoring Refusal ────────────────────────────────────

class TestIranEDScoringRefusal:
    """
    Test 2: Validates that IranEDSource.load_for_evaluation() raises EvaluationRefusedError
    and running evaluate_on_real.py --dataset iran-ed terminates with exit code 2 and
    prints the exact refusal message.
    """

    def test_iran_ed_load_for_evaluation_raises_evaluation_refused_error(self, iran_ed_csv_path: str):
        source = IranEDSource(file_path=iran_ed_csv_path)
        with pytest.raises(EvaluationRefusedError) as exc_info:
            source.load_for_evaluation()

        assert str(exc_info.value) == EXACT_REFUSAL_MESSAGE
        assert (
            "Iran ED triage grade is binary in the published source and is unsupported "
            "for three-tier full-input evaluation; inspection/sparse-input analysis only."
            == str(exc_info.value)
        )

    def test_iran_ed_manifest_scoring_unsupported(self, iran_ed_csv_path: str):
        source = IranEDSource(file_path=iran_ed_csv_path)
        manifest = source._build_manifest(iran_ed_csv_path)
        assert manifest.scoring_supported is False
        assert manifest.input_mode == "not_scored"
        assert "published_binary" in manifest.label_definition

    def test_iran_ed_cli_dataset_refusal_exit_code_and_message(self, iran_ed_csv_path: str):
        script_path = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
        cmd = [
            sys.executable,
            script_path,
            "--dataset",
            "iran-ed",
            "--file",
            iran_ed_csv_path,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        assert proc.returncode == 2
        assert EXACT_REFUSAL_MESSAGE in proc.stderr


# ── Test Suite 3: CDC NHAMCS 2022 Fixed-Width Parsing ────────────────────────

class TestNHAMCS2022FixedProperties:
    """
    Test 3: Validates character offsets against official CDC 2022 specs
    (AGE, SEX, TEMPF, PULSE, RESPR, BPSYS, BPDIAS, POPCT, IMMEDR, PATWT).
    """

    def _make_line(
        self,
        year="2022",
        age=" 25",
        sex="1",
        tempf=" 986",
        pulse=" 75",
        respr=" 16",
        sbp="120",
        dbp=" 80",
        spo2=" 98",
        immedr=" 3",
        patwt="   5432.10",
    ) -> str:
        buf = [" "] * 190
        buf[0:4] = f"{year:<4}"[:4]
        buf[15:18] = f"{age:>3}"[:3]
        buf[24:25] = f"{sex:>1}"[:1]
        buf[47:51] = f"{tempf:>4}"[:4]
        buf[51:54] = f"{pulse:>3}"[:3]
        buf[54:57] = f"{respr:>3}"[:3]
        buf[57:60] = f"{sbp:>3}"[:3]
        buf[60:63] = f"{dbp:>3}"[:3]
        buf[63:66] = f"{spo2:>3}"[:3]
        buf[66:68] = f"{immedr:>2}"[:2]
        buf[178:188] = f"{patwt:>10}"[:10]
        return "".join(buf)

    def test_fixed_width_exact_character_offsets(self):
        line = self._make_line(
            year="2022",
            age=" 45",
            sex="2",
            tempf="1040",
            pulse="115",
            respr="24",
            sbp="150",
            dbp=" 95",
            spo2=" 94",
            immedr=" 1",
            patwt="  12345.67",
        )
        source = NHAMCS2022Source()
        record, insp, reason = source._parse_line(line, line_idx=1)

        assert record is not None
        assert insp is not None
        assert reason is None

        # Verify exact field parsed values
        assert insp["patient_age"] == 45
        assert insp["patient_sex"] == "male"
        assert insp["temperature"] == 40.0
        assert insp["heart_rate"] == 115
        assert insp["respiratory_rate"] == 24
        assert insp["bp_systolic"] == 150
        assert insp["bp_diastolic"] == 95
        assert insp["spo2"] == 94
        assert insp["immedr_code"] == 1
        assert insp["reference_label"] == "EMERGENCY"
        assert insp["patwt"] == 12345.67

    def test_nhamcs_synthetic_fixture_cohort_flow(self, nhamcs_2022_txt_path: str):
        source = NHAMCS2022Source(file_path=nhamcs_2022_txt_path)
        records, counters, manifest = source.load_for_evaluation()

        assert manifest.source_id == "nhamcs_2022"
        assert manifest.scoring_supported is True
        assert manifest.input_mode == "partial_input"

        assert counters.total_records == 17
        assert counters.valid_records == 10
        assert counters.excluded_records == 7

        assert counters.reasons["sentinel_immedr_minus_9"] == 1
        assert counters.reasons["sentinel_immedr_minus_8"] == 1
        assert counters.reasons["sentinel_immedr_0"] == 1
        assert counters.reasons["sentinel_immedr_7"] == 1
        assert counters.reasons["invalid_age"] == 1
        assert counters.reasons["invalid_sex"] == 1
        assert counters.reasons["short_line_format"] == 1

    def test_short_line_format_rejection(self):
        source = NHAMCS2022Source()
        counters = ExclusionCounters()
        rec, insp, reason = source._parse_line("2022 short", line_idx=1, counters=counters)
        assert rec is None
        assert reason == "short_line_format"
        assert counters.reasons["short_line_format"] == 1


# ── Test Suite 4: CDC NHAMCS 2022 Numerical & Categorical Conversions ────────

class TestNHAMCSConversions:
    """
    Test 4: Validates Fahrenheit tenths to Celsius conversion, sex mapping,
    Doppler rejection (998), IMMEDR sentinels (-9, -8, 0, 7), and BP consistency.
    """

    def _parse(self, **kwargs) -> Tuple[Any, Any, Any]:
        source = NHAMCS2022Source()
        buf = [" "] * 190
        buf[0:4] = f"{kwargs.get('year', '2022'):<4}"[:4]
        buf[15:18] = f"{kwargs.get('age', ' 25'):>3}"[:3]
        buf[24:25] = f"{kwargs.get('sex', '1'):>1}"[:1]
        buf[47:51] = f"{kwargs.get('tempf', ' 986'):>4}"[:4]
        buf[51:54] = f"{kwargs.get('pulse', ' 75'):>3}"[:3]
        buf[54:57] = f"{kwargs.get('respr', ' 16'):>3}"[:3]
        buf[57:60] = f"{kwargs.get('sbp', '120'):>3}"[:3]
        buf[60:63] = f"{kwargs.get('dbp', ' 80'):>3}"[:3]
        buf[63:66] = f"{kwargs.get('spo2', ' 98'):>3}"[:3]
        buf[66:68] = f"{kwargs.get('immedr', ' 3'):>2}"[:2]
        buf[178:188] = f"{kwargs.get('patwt', '   5432.10'):>10}"[:10]
        line = "".join(buf)
        counters = ExclusionCounters()
        return source._parse_line(line, line_idx=1, counters=counters)

    def test_fahrenheit_tenths_to_celsius_conversion(self):
        # 98.6°F -> 37.0°C
        rec, insp, _ = self._parse(tempf=" 986")
        assert insp["temperature"] == 37.0

        # 104.0°F -> 40.0°C
        rec, insp, _ = self._parse(tempf="1040")
        assert insp["temperature"] == 40.0

        # 89.6°F (lower bound 896) -> 32.0°C
        rec, insp, _ = self._parse(tempf=" 896")
        assert insp["temperature"] == 32.0

        # 105.6°F (upper bound 1056) -> 40.9°C
        rec, insp, _ = self._parse(tempf="1056")
        assert insp["temperature"] == 40.9

        # Out-of-range temperatures (<896 or >1056) -> None
        rec, insp, _ = self._parse(tempf=" 700")
        assert insp["temperature"] is None

        rec, insp, _ = self._parse(tempf="1200")
        assert insp["temperature"] is None

        # Sentinels -> None
        rec, insp, _ = self._parse(tempf=" -9 ")
        assert insp["temperature"] is None

        rec, insp, _ = self._parse(tempf="9999")
        assert insp["temperature"] is None

    def test_sex_mapping_and_exclusions(self):
        # 1 -> female
        rec, insp, _ = self._parse(sex="1")
        assert insp["patient_sex"] == "female"

        # 2 -> male
        rec, insp, _ = self._parse(sex="2")
        assert insp["patient_sex"] == "male"

        # 0 / blank / other -> invalid_sex exclusion
        rec, insp, reason = self._parse(sex="0")
        assert rec is None
        assert reason == "invalid_sex"

        rec, insp, reason = self._parse(sex=" ")
        assert rec is None
        assert reason == "invalid_sex"

    def test_doppler_rejection_pulse_and_dbp(self):
        # Pulse 998 -> heart_rate None, is_doppler_pulse True
        rec, insp, _ = self._parse(pulse="998")
        assert insp["heart_rate"] is None
        assert insp["is_doppler_pulse"] is True
        assert rec.form_data["heart_rate"] is None

        # DBP 998 -> bp_diastolic None, is_doppler_dbp True
        rec, insp, _ = self._parse(dbp="998")
        assert insp["bp_diastolic"] is None
        assert insp["is_doppler_dbp"] is True
        assert rec.form_data["bp_diastolic"] is None

    def test_immedr_sentinels_granular_exclusion(self):
        for sentinel, expected_reason in [
            ("-9", "sentinel_immedr_minus_9"),
            ("-8", "sentinel_immedr_minus_8"),
            (" 0", "sentinel_immedr_0"),
            ("00", "sentinel_immedr_0"),
            (" 7", "sentinel_immedr_7"),
            ("07", "sentinel_immedr_7"),
            (" 9", "sentinel_immedr_out_of_range"),
            ("xx", "sentinel_immedr_invalid"),
        ]:
            rec, insp, reason = self._parse(immedr=sentinel)
            assert rec is None
            assert reason == expected_reason

    def test_blood_pressure_range_and_physiological_inversion(self):
        # Valid BP
        rec, insp, _ = self._parse(sbp="120", dbp=" 80")
        assert insp["bp_systolic"] == 120
        assert insp["bp_diastolic"] == 80

        # Physiological Inversion (DBP >= SBP) -> Both set to None
        rec, insp, _ = self._parse(sbp="110", dbp="120")
        assert insp["bp_systolic"] is None
        assert insp["bp_diastolic"] is None
        assert rec.form_data["bp_systolic"] is None
        assert rec.form_data["bp_diastolic"] is None

        # Equal SBP and DBP (DBP == SBP) -> Both set to None
        rec, insp, _ = self._parse(sbp="120", dbp="120")
        assert insp["bp_systolic"] is None
        assert insp["bp_diastolic"] is None

        # Zero BP (0/0) -> Both set to None
        rec, insp, _ = self._parse(sbp="  0", dbp="  0")
        assert insp["bp_systolic"] is None
        assert insp["bp_diastolic"] is None

        # Boundary checks
        rec, insp, _ = self._parse(sbp=" 42", dbp=" 80")  # SBP < 43 -> None
        assert insp["bp_systolic"] is None

        rec, insp, _ = self._parse(sbp="290", dbp=" 80")  # SBP > 289 -> None
        assert insp["bp_systolic"] is None

        rec, insp, _ = self._parse(sbp="120", dbp=" 21")  # DBP < 22 -> None
        assert insp["bp_diastolic"] is None

        rec, insp, _ = self._parse(sbp="200", dbp="191")  # DBP > 190 -> None
        assert insp["bp_diastolic"] is None

    def test_age_parsing_and_top_coding(self):
        # Infant (age 0)
        rec, insp, _ = self._parse(age="  0")
        assert insp["patient_age"] == 0

        # Adult (age 25)
        rec, insp, _ = self._parse(age=" 25")
        assert insp["patient_age"] == 25

        # Elderly top-coded (age 94)
        rec, insp, _ = self._parse(age=" 94")
        assert insp["patient_age"] == 94

        # Age > 94 (e.g. 95) -> excluded
        rec, insp, reason = self._parse(age=" 95")
        assert rec is None
        assert reason == "invalid_age"


# ── Test Suite 5: CDC NHAMCS 2022 Proxy Mapping & Partial Input Mode ─────────

class TestNHAMCSProxyAndPartialInput:
    """
    Test 5: Validates nhamcs_immediacy_v1 proxy mapping (1/2 -> EMERGENCY, 3 -> URGENT, 4/5 -> ROUTINE)
    and partial-input mode enforcement (empty chief complaint & symptoms, is_partial_input is True).
    """

    def _parse(self, immedr_val: str) -> CanonicalPatientRecord:
        source = NHAMCS2022Source()
        buf = [" "] * 190
        buf[0:4] = "2022"
        buf[15:18] = " 30"
        buf[24:25] = "1"
        buf[47:51] = " 986"
        buf[51:54] = " 75"
        buf[54:57] = " 16"
        buf[57:60] = "120"
        buf[60:63] = " 80"
        buf[63:66] = " 98"
        buf[66:68] = f"{immedr_val:>2}"[:2]
        buf[178:188] = "   5000.00"
        rec, _, _ = source._parse_line("".join(buf), line_idx=1)
        return rec

    def test_nhamcs_immediacy_v1_proxy_mapping(self):
        # 1 -> EMERGENCY
        rec1 = self._parse(" 1")
        assert rec1.reference_label == "EMERGENCY"
        assert rec1.reference_tier_index == 2

        # 2 -> EMERGENCY
        rec2 = self._parse(" 2")
        assert rec2.reference_label == "EMERGENCY"
        assert rec2.reference_tier_index == 2

        # 3 -> URGENT
        rec3 = self._parse(" 3")
        assert rec3.reference_label == "URGENT"
        assert rec3.reference_tier_index == 1

        # 4 -> ROUTINE
        rec4 = self._parse(" 4")
        assert rec4.reference_label == "ROUTINE"
        assert rec4.reference_tier_index == 0

        # 5 -> ROUTINE
        rec5 = self._parse(" 5")
        assert rec5.reference_label == "ROUTINE"
        assert rec5.reference_tier_index == 0

    def test_strict_partial_input_enforcement(self, nhamcs_2022_txt_path: str):
        source = NHAMCS2022Source(file_path=nhamcs_2022_txt_path)
        records, _, _ = source.load_for_evaluation()

        assert len(records) > 0
        for rec in records:
            assert rec.is_partial_input is True
            assert rec.form_data["chief_complaint"] == ""
            assert rec.form_data["symptoms"] == []
            assert rec.form_data["chief_complaint_available"] is False
            assert rec.form_data["observations"] == ""
            assert rec.form_data["known_conditions"] == ""
            assert rec.form_data["current_medications"] == ""
            assert rec.form_data["location"] == ""
            assert rec.form_data["complaint_duration"] == ""

        dq = source.inspect()
        assert dq.extra_metadata["chief_complaint_available"] is False

    def test_nhamcs_model_inference_on_partial_input(self, nhamcs_2022_txt_path: str):
        source = NHAMCS2022Source(file_path=nhamcs_2022_txt_path)
        records, _, _ = source.load_for_evaluation()

        clf_mod.load_classifier()
        for rec in records:
            res = clf_mod.predict_triage(rec.form_data)
            assert "triage_level" in res
            assert res["triage_level"] in ("ROUTINE", "URGENT", "EMERGENCY")
            assert "confidence_score" in res


# ── Test Suite 6: CDC NHAMCS 2022 Unweighted Metrics ─────────────────────────

class TestNHAMCSUnweightedMetrics:
    """
    Test 6: Validates that survey weights (PATWT) are stored in metadata only
    and never used to weight model discrimination metrics (sensitivity, specificity, confusion matrix).
    """

    def test_patwt_stored_in_records_and_metadata_only(self, nhamcs_2022_txt_path: str):
        source = NHAMCS2022Source(file_path=nhamcs_2022_txt_path)
        dq: AggregateDataQuality = source.inspect()

        # Metadata stores survey design stats
        survey_meta = dq.extra_metadata["survey_design_metadata"]
        assert survey_meta["patwt_sampled_encounters"] == 10
        assert survey_meta["patwt_sum_population_estimate"] > 0
        assert survey_meta["patwt_mean"] > 0
        assert "Strictly excluded from model performance weighting." in survey_meta["survey_weight_policy"]

        # Record stores survey weight
        records, _, _ = source.load_for_evaluation()
        for rec in records:
            assert rec.survey_weight is not None
            assert rec.survey_weight > 0

    def test_metrics_calculation_strictly_unweighted(self):
        # 4 records: 2 Emergency, 1 Urgent, 1 Routine
        y_ref = np.array([2, 2, 1, 0], dtype=int)
        y_prod = np.array([2, 1, 1, 0], dtype=int)
        y_raw = np.array([2, 1, 1, 0], dtype=int)
        conf = np.array([0.9, 0.8, 0.85, 0.95], dtype=float)
        guardrail = np.array([False, False, False, False], dtype=bool)
        formdatas = [
            {"patient_age": 30, "patient_sex": "male"},
            {"patient_age": 40, "patient_sex": "female"},
            {"patient_age": 50, "patient_sex": "male"},
            {"patient_age": 60, "patient_sex": "female"},
        ]

        metrics = calculate_evaluation_metrics(
            y_ref=y_ref,
            y_prod=y_prod,
            y_raw=y_raw,
            conf=conf,
            guardrail=guardrail,
            formdatas=formdatas,
        )

        # EMERGENCY: 2 total, 1 TP, 1 FN -> Sensitivity = 1/2 = 0.50
        em_sens = metrics["discrimination"]["EMERGENCY"]["sensitivity"]
        assert em_sens["k"] == 1
        assert em_sens["n"] == 2
        assert em_sens["point"] == 0.50

        # Confusion matrix is unweighted integer counts
        cm = metrics["confusion_matrix"]
        assert cm[2][2] == 1  # ref=EMERGENCY, pred=EMERGENCY
        assert cm[2][1] == 1  # ref=EMERGENCY, pred=URGENT
        assert cm[1][1] == 1  # ref=URGENT, pred=URGENT
        assert cm[0][0] == 1  # ref=ROUTINE, pred=ROUTINE


# ── Test Suite 7: Aggregate-Only JSON Report Contract ────────────────────────

class TestAggregateOnlyJSONReportContract:
    """
    Test 7: Validates that JSON output contains required metadata, SHA-256 checksum,
    performance metrics (raw vs guardrail), ECE calibration diagnostic disclaimer,
    and strictly contains ZERO row-level patient records or free text.
    """

    def test_inspection_json_report_schema_and_zero_leakage(self, nhamcs_2022_txt_path: str):
        source = NHAMCS2022Source(file_path=nhamcs_2022_txt_path)
        dq: AggregateDataQuality = source.inspect()

        report = build_inspection_json_report(dq)

        # Assert mandatory top-level keys
        assert "source_manifest" in report
        assert "execution_mode" in report
        assert report["execution_mode"] == "inspection"
        assert "cohort_flow" in report
        assert "data_quality" in report
        assert "limitations_and_non_claims" in report

        # Assert manifest contents
        manifest = report["source_manifest"]
        assert manifest["source_id"] == "nhamcs_2022"
        assert manifest["file_sha256"] == compute_file_sha256(nhamcs_2022_txt_path)
        assert manifest["input_mode"] == "partial_input"

        # Assert limitations list
        assert len(report["limitations_and_non_claims"]) >= 5

        # STRICT: Zero patient-level data leakage
        assert_zero_patient_leakage(report)

    def test_evaluation_json_report_schema_and_zero_leakage(self, nhamcs_2022_txt_path: str):
        source = NHAMCS2022Source(file_path=nhamcs_2022_txt_path)
        records, counters, manifest = source.load_for_evaluation()

        clf_mod.load_classifier()
        formdatas = [r.form_data for r in records]
        y_ref = np.array([r.reference_tier_index for r in records], dtype=int)
        y_prod = np.zeros(len(records), dtype=int)
        y_raw = np.zeros(len(records), dtype=int)
        conf = np.zeros(len(records), dtype=float)
        guardrail = np.zeros(len(records), dtype=bool)

        for i, fd in enumerate(formdatas):
            res = clf_mod.predict_triage(fd)
            y_prod[i] = TIER_INDICES[res["triage_level"]]
            conf[i] = float(res.get("confidence_score", 1.0))

        metrics = calculate_evaluation_metrics(
            y_ref=y_ref,
            y_prod=y_prod,
            y_raw=y_raw,
            conf=conf,
            guardrail=guardrail,
            formdatas=formdatas,
        )

        report = build_evaluation_json_report(manifest, counters, metrics, formdatas)

        # Assert required keys
        assert report["execution_mode"] == "evaluation"
        assert "metrics" in report
        assert "discrimination" in report["metrics"]
        assert "safety_metrics" in report["metrics"]
        assert "guardrail_lift" in report["metrics"]
        assert "calibration_diagnostic" in report["metrics"]

        # ECE calibration disclaimer
        calib = report["metrics"]["calibration_diagnostic"]
        assert "ece" in calib
        assert "Limited predicted-class confidence diagnostic only" in calib["diagnostic_disclaimer"]

        # STRICT: Zero patient-level data leakage
        assert_zero_patient_leakage(report)

    def test_assert_zero_patient_leakage_adversarial_detection(self):
        # Clean dictionary passes
        clean = {
            "source_manifest": {"source_name": "Test"},
            "metrics": {"discrimination": {"accuracy": 0.95}},
        }
        assert_zero_patient_leakage(clean)

        # Forbidden patient row / leakage key raises AssertionError
        for forbidden_key in [
            "form_data",
            "raw_fields",
            "patient_records",
            "patient_id",
            "mrn",
            "patient_name",
            "free_text",
        ]:
            bad_dict = {"metrics": {forbidden_key: [{"age": 25}]}}
            with pytest.raises(AssertionError) as exc_info:
                assert_zero_patient_leakage(bad_dict)
            assert f"forbidden key '{forbidden_key}'" in str(exc_info.value)


# ── Test Suite 8: Generic CSV and Self-Test Backward Compatibility ───────────

class TestBackwardCompatibility:
    """
    Test 8: Validates generic CSV parsing (ESI/KTAS acuity mapping, symptom extraction)
    and self-test backward compatibility without regressions.
    """

    def test_generic_csv_acuity_mapping(self):
        # ESI: 1, 2 -> EMERGENCY (2); 3 -> URGENT (1); 4, 5 -> ROUTINE (0)
        assert parse_reference_tier({"acuity": 1}, acuity_scale="esi") == "EMERGENCY"
        assert parse_reference_tier({"acuity": 2}, acuity_scale="esi") == "EMERGENCY"
        assert parse_reference_tier({"acuity": 3}, acuity_scale="esi") == "URGENT"
        assert parse_reference_tier({"acuity": 4}, acuity_scale="esi") == "ROUTINE"
        assert parse_reference_tier({"acuity": 5}, acuity_scale="esi") == "ROUTINE"

        # Direct tier string
        assert parse_reference_tier({"tier": "EMERGENCY"}) == "EMERGENCY"
        assert parse_reference_tier({"tier": "URGENT"}) == "URGENT"
        assert parse_reference_tier({"tier": "ROUTINE"}) == "ROUTINE"
        assert parse_reference_tier({"tier": "2"}) == "EMERGENCY"
        assert parse_reference_tier({"tier": "1"}) == "URGENT"
        assert parse_reference_tier({"tier": "0"}) == "ROUTINE"

    def test_generic_csv_row_to_formdata_symptoms_and_temp(self):
        row = {
            "age": "35",
            "gender": "female",
            "sbp": "120",
            "dbp": "80",
            "heartrate": "72",
            "temp": "100.4",
            "symptoms": "chest_pain,breathlessness,unknown_symptom_xyz",
            "chiefcomplaint": "chest pain and shortness of breath",
        }
        # Temp in Fahrenheit -> converted to Celsius: (100.4 - 32) * 5/9 = 38.0
        fd = row_to_formdata(row, temp_fahrenheit=True)

        assert fd["patient_age"] == 35
        assert fd["patient_sex"] == "female"
        assert fd["bp_systolic"] == 120
        assert fd["bp_diastolic"] == 80
        assert fd["heart_rate"] == 72
        assert fd["temperature"] == 38.0
        assert "chest_pain" in fd["symptoms"]
        assert "breathlessness" in fd["symptoms"]
        assert "unknown_symptom_xyz" not in fd["symptoms"]  # Dropped from allowlist

    def test_synthetic_self_test_source(self):
        source = SyntheticSelfTestSource(n=50, seed=2026)
        dq: AggregateDataQuality = source.inspect()

        assert dq.total_records_inspected == 50
        assert dq.source_manifest.source_id == "synthetic_self_test"
        assert dq.complete_vitals_count > 0

        records, counters, manifest = source.load_for_evaluation()
        assert len(records) == 50
        assert counters.valid_records == 50
        for rec in records:
            assert rec.reference_label in ("ROUTINE", "URGENT", "EMERGENCY")

    def test_self_test_run_evaluation(self):
        metrics = run_evaluation(source_id="self-test", n=50, seed=2026)
        assert "confusion_matrix" in metrics
        assert "overall_agreement" in metrics
        assert "discrimination" in metrics
        assert "safety_metrics" in metrics
        assert "guardrail_lift" in metrics
        assert "calibration_diagnostic" in metrics


# ── Test Suite 9: CLI End-to-End Execution & Output Schema Validation ────────

class TestCLIE2EExecutionAndOutputSchema:
    """
    Test 9: Validates end-to-end CLI execution for inspection, evaluation, self-test,
    and output JSON schema conformity with zero patient-level data leakage.
    """

    def test_cli_iran_ed_inspection_json_report_e2e(self, iran_ed_csv_path: str, iran_ed_admission_path: str, tmp_path):
        script_path = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
        out_json = str(tmp_path / "iran_inspection.json")
        cmd = [
            sys.executable,
            script_path,
            "--inspect-source",
            "iran-ed",
            "--file",
            iran_ed_csv_path,
            "--linkage-file",
            iran_ed_admission_path,
            "--json-out",
            out_json,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"CLI execution failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        assert os.path.isfile(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert report["execution_mode"] == "inspection"
        assert report["source_manifest"]["source_id"] == "iran_ed"
        assert report["source_manifest"]["file_sha256"] == compute_file_sha256(iran_ed_csv_path)
        assert report["data_quality"]["linkage_summary"]["status"] == "linked"
        assert len(report["limitations_and_non_claims"]) >= 5
        assert_zero_patient_leakage(report)

    def test_cli_nhamcs_2022_inspection_json_report_e2e(self, nhamcs_2022_txt_path: str, tmp_path):
        script_path = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
        out_json = str(tmp_path / "nhamcs_inspection.json")
        cmd = [
            sys.executable,
            script_path,
            "--inspect-source",
            "nhamcs-2022",
            "--file",
            nhamcs_2022_txt_path,
            "--json-out",
            out_json,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"CLI execution failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        assert os.path.isfile(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert report["execution_mode"] == "inspection"
        assert report["source_manifest"]["source_id"] == "nhamcs_2022"
        assert report["source_manifest"]["input_mode"] == "partial_input"
        assert "survey_design_metadata" in report["data_quality"]["extra_metadata"]
        assert_zero_patient_leakage(report)

    def test_cli_nhamcs_2022_evaluation_json_report_e2e(self, nhamcs_2022_txt_path: str, tmp_path):
        script_path = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
        out_json = str(tmp_path / "nhamcs_evaluation.json")
        cmd = [
            sys.executable,
            script_path,
            "--dataset",
            "nhamcs-2022",
            "--file",
            nhamcs_2022_txt_path,
            "--json-out",
            out_json,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"CLI execution failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        assert os.path.isfile(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert report["execution_mode"] == "evaluation"
        assert report["source_manifest"]["source_id"] == "nhamcs_2022"
        assert report["source_manifest"]["input_mode"] == "partial_input"
        assert "confusion_matrix" in report["metrics"]
        assert "discrimination" in report["metrics"]
        assert "safety_metrics" in report["metrics"]
        assert "guardrail_lift" in report["metrics"]
        assert "calibration_diagnostic" in report["metrics"]
        assert "ece" in report["metrics"]["calibration_diagnostic"]
        assert_zero_patient_leakage(report)

    def test_cli_generic_csv_evaluation_e2e(self, tmp_path):
        csv_path = str(tmp_path / "generic_test.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["age", "gender", "sbp", "dbp", "heartrate", "temp", "acuity"])
            writer.writerow(["45", "female", "120", "80", "72", "37.0", "3"])
            writer.writerow(["60", "male", "160", "100", "110", "38.5", "1"])
            writer.writerow(["25", "female", "115", "75", "68", "36.8", "5"])

        script_path = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
        out_json = str(tmp_path / "generic_eval.json")
        cmd = [
            sys.executable,
            script_path,
            "--csv",
            csv_path,
            "--acuity-scale",
            "esi",
            "--json-out",
            out_json,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"CLI execution failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        assert os.path.isfile(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert report["execution_mode"] == "evaluation"
        assert "metrics" in report
        assert_zero_patient_leakage(report)

    def test_cli_self_test_e2e(self, tmp_path):
        script_path = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
        out_json = str(tmp_path / "selftest_eval.json")
        cmd = [
            sys.executable,
            script_path,
            "--self-test",
            "--n",
            "20",
            "--seed",
            "2026",
            "--json-out",
            out_json,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"CLI execution failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        assert os.path.isfile(out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            report = json.load(f)

        assert report["execution_mode"] == "evaluation"
        assert report["source_manifest"]["source_id"] == "synthetic_self_test"
        assert report["cohort_flow"]["total_records"] == 20
        assert_zero_patient_leakage(report)

    def test_cli_missing_required_arguments_returns_non_zero(self):
        script_path = os.path.join(TOOLS_DIR, "evaluate_on_real.py")
        proc = subprocess.run([sys.executable, script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode != 0
        assert "Must provide --inspect-source, --dataset/--source, --csv, or --self-test" in proc.stderr
