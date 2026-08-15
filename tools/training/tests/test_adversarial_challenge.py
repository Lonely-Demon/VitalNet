"""
Adversarial Stress Test Suite — Milestone M4 Empirical Challenger.

Conducts rigorous adversarial verification across all required and extended dimensions:
1. Challenge 1: Fixed-width parsing boundaries & malformed inputs (exact character offsets, line length boundaries, tabs, non-numeric values, field shift attacks).
2. Challenge 2: Conversion boundaries & sentinels (temperature, pulse, SBP, DBP, physiological inversion, edge cases).
3. Challenge 3: Adversarial Data Leakage Injection (deep JSON trees, casing, forbidden keys, missingness exceptions, cyclic/list-of-tuples structures).
4. Challenge 4: Survey weight independence (Wilson CIs, confusion matrix, metrics invariance under PATWT variation).
5. Challenge 5: Iran ED inspection edge cases & admission linkage stress testing.
6. Challenge 6: Mathematical & statistical edge cases (Wilson score interval extremes).
"""

import copy
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
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
    AggregateDataQuality,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    ExclusionCounters,
    IranEDSource,
    NHAMCS2022Source,
    NHAMCS_IMMEDIACY_V1,
    PUBLISHED_HEADERS,
    SourceManifest,
    TIER_INDICES,
    TIER_NAMES,
)
from evaluate_on_real import (
    FORBIDDEN_LEAKAGE_KEYS,
    assert_zero_patient_leakage,
    build_evaluation_json_report,
    build_inspection_json_report,
    calculate_evaluation_metrics,
    wilson,
    wilson_dict,
)


def _build_fixed_line(
    vyear: str = "2022",
    age: str = " 25",
    sex: str = "1",
    tempf: str = " 986",
    pulse: str = " 75",
    respr: str = " 16",
    sbp: str = "120",
    dbp: str = " 80",
    spo2: str = " 98",
    immedr: str = " 3",
    patwt: str = "   5432.10",
    total_length: int = 190,
) -> str:
    """Builds a fixed-width line with exact character placements."""
    buf = [" "] * total_length
    buf[0:4] = f"{vyear:<4}"[:4]
    buf[15:18] = f"{age:>3}"[:3]
    buf[24:25] = f"{sex:>1}"[:1]
    buf[47:51] = f"{tempf:>4}"[:4]
    buf[51:54] = f"{pulse:>3}"[:3]
    buf[54:57] = f"{respr:>3}"[:3]
    buf[57:60] = f"{sbp:>3}"[:3]
    buf[60:63] = f"{dbp:>3}"[:3]
    buf[63:66] = f"{spo2:>3}"[:3]
    buf[66:68] = f"{immedr:>2}"[:2]
    if total_length >= 188:
        buf[178:188] = f"{patwt:>10}"[:10]
    return "".join(buf)


# ═══════════════════════════════════════════════════════════════════════════════
# Challenge 1: Fixed-Width Parsing Boundaries & Malformed Inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestChallenge1FixedWidthBoundaries:
    """
    Stress-tests exact CDC NHAMCS fixed-width column offsets, line lengths,
    tab characters, non-numeric values, and missing fields.
    """

    def test_exact_character_offsets_isolation(self):
        """Verify each field is read strictly from its designated character range."""
        source = NHAMCS2022Source()

        # Base line with unique identifiable values
        line = _build_fixed_line(
            vyear="2022",
            age=" 42",      # [15:18]
            sex="2",        # [24:25] (male)
            tempf="1004",   # [47:51] (38.0°C)
            pulse=" 88",    # [51:54]
            respr=" 20",    # [54:57]
            sbp="135",      # [57:60]
            dbp=" 85",      # [60:63]
            spo2=" 97",     # [63:66]
            immedr=" 2",    # [66:68] (EMERGENCY)
            patwt="  12345.67", # [178:188]
        )

        rec, insp, reason = source._parse_line(line, line_idx=1)
        assert rec is not None
        assert insp is not None
        assert reason is None
        assert insp["patient_age"] == 42
        assert insp["patient_sex"] == "male"
        assert insp["temperature"] == 38.0
        assert insp["heart_rate"] == 88
        assert insp["respiratory_rate"] == 20
        assert insp["bp_systolic"] == 135
        assert insp["bp_diastolic"] == 85
        assert insp["spo2"] == 97
        assert insp["immedr_code"] == 2
        assert insp["reference_label"] == "EMERGENCY"
        assert insp["patwt"] == 12345.67

    def test_field_shift_attacks(self):
        """
        Shift values by 1 character left or right and verify that field parsing
        either rejects invalid format or maps out-of-boundary values safely.
        """
        source = NHAMCS2022Source()

        # Age shifted left by 1 (occupying [14:17] instead of [15:18])
        # If [14:17] has ' 25' and [17] has ' ' -> line[15:18] reads '25 ' -> int('25 ') = 25 (handled by strip)
        # But if shifted further left: [13:16] has ' 25' and [16:18] has '  ' -> line[15:18] reads '5  ' -> int('5  ') = 5
        buf = list(" " * 190)
        buf[0:4] = "2022"
        buf[13:16] = " 25" # shifted 2 chars left
        buf[24:25] = "1"
        buf[66:68] = " 3"
        rec, insp, _ = source._parse_line("".join(buf), line_idx=1)
        assert insp["patient_age"] == 5 # strictly parses [15:18]

    def test_line_length_boundary_conditions(self):
        """Test lines of varying lengths: 0, 50, 67, 68, 187, 188, 500 chars."""
        source = NHAMCS2022Source()

        # 1. Length 0 (empty line) -> short_line_format
        counters = ExclusionCounters()
        rec, insp, reason = source._parse_line("", line_idx=1, counters=counters)
        assert rec is None
        assert reason == "short_line_format"

        # 2. Length 50 chars -> short_line_format
        rec, insp, reason = source._parse_line(" " * 50, line_idx=1, counters=counters)
        assert rec is None
        assert reason == "short_line_format"

        # 3. Length 67 chars -> short_line_format (just below minimum 68)
        rec, insp, reason = source._parse_line(" " * 67, line_idx=1, counters=counters)
        assert rec is None
        assert reason == "short_line_format"

        # 4. Length exactly 68 chars -> valid minimum line, patwt is None
        line_68 = _build_fixed_line(total_length=68)
        assert len(line_68) == 68
        rec, insp, reason = source._parse_line(line_68, line_idx=1, counters=counters)
        assert rec is not None
        assert insp["patwt"] is None
        assert rec.survey_weight is None

        # 5. Length 187 chars (1 char short of PATWT [178:188]) -> accepted, patwt is None
        line_187 = _build_fixed_line(total_length=187)
        assert len(line_187) == 187
        rec, insp, reason = source._parse_line(line_187, line_idx=1, counters=counters)
        assert rec is not None
        assert insp["patwt"] is None

        # 6. Length exactly 188 chars -> accepted, patwt parsed
        line_188 = _build_fixed_line(patwt="   1234.50", total_length=188)
        assert len(line_188) == 188
        rec, insp, reason = source._parse_line(line_188, line_idx=1, counters=counters)
        assert rec is not None
        assert insp["patwt"] == 1234.50

        # 7. Length 500 chars -> accepted, trailing padding ignored
        line_500 = _build_fixed_line(patwt="   9999.99", total_length=500)
        assert len(line_500) == 500
        rec, insp, reason = source._parse_line(line_500, line_idx=1, counters=counters)
        assert rec is not None
        assert insp["patwt"] == 9999.99
        assert insp["patient_age"] == 25

    def test_tab_characters_in_fixed_width_line(self):
        """Test presence of tab characters: ensure robust non-crashing behavior."""
        source = NHAMCS2022Source()

        # Tab in age column
        line_tab_age = _build_fixed_line(age="\t25")
        rec, insp, reason = source._parse_line(line_tab_age, line_idx=1)
        assert insp["patient_age"] == 25

        # All tabs in age column -> invalid_age
        line_tab_only = _build_fixed_line(age="\t\t\t")
        rec, insp, reason = source._parse_line(line_tab_only, line_idx=1)
        assert rec is None
        assert reason == "invalid_age"

    def test_non_numeric_values_in_all_columns(self):
        """Test non-numeric values (strings, symbols, NaNs) across all fields."""
        source = NHAMCS2022Source()

        # Non-numeric AGE -> invalid_age
        for bad_age in ["ABC", "NaN", "###", "1.5"]:
            rec, insp, reason = source._parse_line(_build_fixed_line(age=bad_age), line_idx=1)
            assert rec is None
            assert reason == "invalid_age"

        # Non-numeric SEX -> invalid_sex
        for bad_sex in ["F", "M", "X", "#"]:
            rec, insp, reason = source._parse_line(_build_fixed_line(sex=bad_sex), line_idx=1)
            assert rec is None
            assert reason == "invalid_sex"

        # Non-numeric vitals -> mapped to None (not crashing, encounter still valid)
        line_bad_vitals = _build_fixed_line(
            tempf="TEMP",
            pulse="PLS",
            respr="RSP",
            sbp="SYS",
            dbp="DIA",
            spo2="SAT",
            patwt="  INVALID!",
        )
        rec, insp, reason = source._parse_line(line_bad_vitals, line_idx=1)
        assert rec is not None
        assert insp["temperature"] is None
        assert insp["heart_rate"] == None
        assert insp["respiratory_rate"] is None
        assert insp["bp_systolic"] is None
        assert insp["bp_diastolic"] is None
        assert insp["spo2"] is None
        assert insp["patwt"] is None
        assert insp["reference_label"] == "URGENT"

        # Non-numeric IMMEDR -> sentinel_immedr_invalid
        for bad_imm in ["IM", "NA", "??"]:
            rec, insp, reason = source._parse_line(_build_fixed_line(immedr=bad_imm), line_idx=1)
            assert rec is None
            assert reason == "sentinel_immedr_invalid"


# ═══════════════════════════════════════════════════════════════════════════════
# Challenge 2: Conversion Boundaries & Sentinels
# ═══════════════════════════════════════════════════════════════════════════════

class TestChallenge2ConversionBoundariesAndSentinels:
    """
    Stress-tests exact mathematical boundaries and sentinel codes for
    temperature, pulse, SBP, DBP, and physiological inversion.
    """

    def _parse(self, **kwargs) -> Tuple[Any, Any, Any]:
        source = NHAMCS2022Source()
        line = _build_fixed_line(**kwargs)
        counters = ExclusionCounters()
        return source._parse_line(line, line_idx=1, counters=counters)

    def test_temperature_boundary_precision(self):
        """
        Test temperature:
        895 (out of bounds <896) -> None
        896 (in bounds, 89.6°F) -> (89.6 - 32) * 5 / 9 = 32.0°C
        1056 (in bounds, 105.6°F) -> (105.6 - 32) * 5 / 9 = 40.8888... -> 40.9°C
        1057 (out of bounds >1056) -> None
        """
        # 895 -> None
        rec, insp, _ = self._parse(tempf=" 895")
        assert insp["temperature"] is None

        # 896 -> 32.0°C
        rec, insp, _ = self._parse(tempf=" 896")
        assert insp["temperature"] == 32.0

        # 1056 -> 40.9°C
        rec, insp, _ = self._parse(tempf="1056")
        assert insp["temperature"] == 40.9

        # 1057 -> None
        rec, insp, _ = self._parse(tempf="1057")
        assert insp["temperature"] is None

    def test_pulse_boundary_and_sentinels(self):
        """
        Test pulse:
        0 (in bounds) -> 0
        240 (in bounds) -> 240
        241 (out of bounds >240) -> None
        998 (Doppler) -> None, is_doppler_pulse=True
        -9, -8 (Sentinels) -> None
        """
        rec, insp, _ = self._parse(pulse="  0")
        assert insp["heart_rate"] == 0
        assert insp["is_doppler_pulse"] is False

        rec, insp, _ = self._parse(pulse="240")
        assert insp["heart_rate"] == 240
        assert insp["is_doppler_pulse"] is False

        rec, insp, _ = self._parse(pulse="241")
        assert insp["heart_rate"] is None
        assert insp["is_doppler_pulse"] is False

        rec, insp, _ = self._parse(pulse="998")
        assert insp["heart_rate"] is None
        assert insp["is_doppler_pulse"] is True

        rec, insp, _ = self._parse(pulse=" -9")
        assert insp["heart_rate"] is None

        rec, insp, _ = self._parse(pulse=" -8")
        assert insp["heart_rate"] is None

    def test_systolic_bp_boundaries_and_sentinels(self):
        """
        Test SBP:
        0 (sentinel) -> None
        42 (out of bounds <43) -> None
        43 (in bounds) -> 43
        289 (in bounds) -> 289
        290 (out of bounds >289) -> None
        -9, -8, 000 (sentinels) -> None
        """
        # SBP 0 -> None
        rec, insp, _ = self._parse(sbp="  0", dbp=" 80")
        assert insp["bp_systolic"] is None
        assert insp["bp_diastolic"] == 80  # DBP remains valid

        # SBP 42 -> None
        rec, insp, _ = self._parse(sbp=" 42", dbp=" 30")
        assert insp["bp_systolic"] is None

        # SBP 43 -> 43 (with DBP 30 < 43)
        rec, insp, _ = self._parse(sbp=" 43", dbp=" 30")
        assert insp["bp_systolic"] == 43
        assert insp["bp_diastolic"] == 30

        # SBP 289 -> 289
        rec, insp, _ = self._parse(sbp="289", dbp="100")
        assert insp["bp_systolic"] == 289
        assert insp["bp_diastolic"] == 100

        # SBP 290 -> None
        rec, insp, _ = self._parse(sbp="290", dbp="100")
        assert insp["bp_systolic"] is None

        # SBP 000 / -9 -> None
        rec, insp, _ = self._parse(sbp="000", dbp=" 80")
        assert insp["bp_systolic"] is None
        rec, insp, _ = self._parse(sbp=" -9", dbp=" 80")
        assert insp["bp_systolic"] is None

    def test_diastolic_bp_boundaries_and_sentinels(self):
        """
        Test DBP:
        0 (sentinel) -> None
        21 (out of bounds <22) -> None
        22 (in bounds) -> 22
        190 (in bounds) -> 190
        191 (out of bounds >190) -> None
        998 (Doppler) -> None, is_doppler_dbp=True
        -9, -8, 000 (sentinels) -> None
        """
        # DBP 0 -> None
        rec, insp, _ = self._parse(sbp="120", dbp="  0")
        assert insp["bp_diastolic"] is None
        assert insp["bp_systolic"] == 120

        # DBP 21 -> None
        rec, insp, _ = self._parse(sbp="120", dbp=" 21")
        assert insp["bp_diastolic"] is None

        # DBP 22 -> 22
        rec, insp, _ = self._parse(sbp="120", dbp=" 22")
        assert insp["bp_diastolic"] == 22

        # DBP 190 -> 190 (with SBP 200 > 190)
        rec, insp, _ = self._parse(sbp="200", dbp="190")
        assert insp["bp_diastolic"] == 190
        assert insp["bp_systolic"] == 200

        # DBP 191 -> None
        rec, insp, _ = self._parse(sbp="200", dbp="191")
        assert insp["bp_diastolic"] is None

        # DBP 998 (Doppler) -> None, is_doppler_dbp=True
        rec, insp, _ = self._parse(sbp="120", dbp="998")
        assert insp["bp_diastolic"] is None
        assert insp["is_doppler_dbp"] is True

    def test_physiological_inversion_scenarios(self):
        """
        Test physiological inversion DBP >= SBP:
        - DBP > SBP (e.g. 110/120) -> Both None
        - DBP == SBP (e.g. 120/120) -> Both None
        - DBP < SBP (e.g. 120/80) -> Preserved
        """
        # Inversion 1: DBP 120, SBP 100
        rec, insp, _ = self._parse(sbp="100", dbp="120")
        assert insp["bp_systolic"] is None
        assert insp["bp_diastolic"] is None
        assert rec.form_data["bp_systolic"] is None
        assert rec.form_data["bp_diastolic"] is None

        # Inversion 2: DBP 80, SBP 80 (equality)
        rec, insp, _ = self._parse(sbp=" 80", dbp=" 80")
        assert insp["bp_systolic"] is None
        assert insp["bp_diastolic"] is None

        # Normal: DBP 80, SBP 120
        rec, insp, _ = self._parse(sbp="120", dbp=" 80")
        assert insp["bp_systolic"] == 120
        assert insp["bp_diastolic"] == 80


# ═══════════════════════════════════════════════════════════════════════════════
# Challenge 3: Adversarial Data Leakage Injection
# ═══════════════════════════════════════════════════════════════════════════════

class TestChallenge3AdversarialDataLeakageInjection:
    """
    Stress-tests assert_zero_patient_leakage against adversarial injection of
    patient records, identifiers, free-text strings, casing variations, and deep nestings.
    """

    def test_leakage_detection_all_forbidden_keys(self):
        """Verify that every single forbidden key triggers an AssertionError."""
        for forbidden_key in FORBIDDEN_LEAKAGE_KEYS:
            bad_dict = {
                "source_manifest": {"source_name": "Test"},
                "metrics": {
                    forbidden_key: "patient_value_sample"
                },
            }
            with pytest.raises(AssertionError) as exc_info:
                assert_zero_patient_leakage(bad_dict)
            assert f"forbidden key '{forbidden_key}'" in str(exc_info.value).lower()

    def test_leakage_detection_case_insensitivity(self):
        """Verify that upper-case and mixed-case forbidden keys are caught."""
        for bad_key in [
            "PATIENT_ID",
            "Patient_Name",
            "MRN",
            "Chief_Complaint",
            "FREE_TEXT",
            "Raw_Fields",
            "FORM_DATA",
        ]:
            bad_dict = {"metrics": {bad_key: "leaked_info"}}
            with pytest.raises(AssertionError) as exc_info:
                assert_zero_patient_leakage(bad_dict)
            assert "forbidden key" in str(exc_info.value).lower()

    def test_deeply_nested_leakage_injection(self):
        """Verify leakage detection 7 levels deep inside dicts and lists."""
        deep_dict = {
            "level1": {
                "level2": [
                    {"level3": {
                        "level4": [
                            {"level5": {
                                "level6": {
                                    "mrn": "12345678"
                                }
                            }}
                        ]
                    }}
                ]
            }
        }
        with pytest.raises(AssertionError) as exc_info:
            assert_zero_patient_leakage(deep_dict)
        assert "forbidden key 'mrn'" in str(exc_info.value)

    def test_field_missingness_exception_legitimacy(self):
        """
        Verify that aggregate dictionaries named 'field_missingness' or 'missingness_by_field'
        can legitimately contain column headers like 'chief_complaint' or 'symptoms',
        while patient record fields outside those dictionaries trigger an immediate error.
        """
        # Legitimate aggregate report with missingness on chief_complaint
        clean_report = {
            "source_manifest": {"source_name": "Valid Report"},
            "data_quality": {
                "field_missingness": {
                    "chief_complaint": {"missing_count": 10, "valid_count": 90, "missing_pct": 10.0},
                    "symptoms": {"missing_count": 0, "valid_count": 100, "missing_pct": 0.0},
                },
                "missingness_by_field": {
                    "chief_complaint": {"missing_count": 10, "valid_count": 90, "missing_pct": 10.0},
                }
            }
        }
        # Must pass without error
        assert_zero_patient_leakage(clean_report)

        # But if 'chief_complaint' appears under 'metrics' or 'data_quality' directly -> AssertionError
        corrupt_report = copy.deepcopy(clean_report)
        corrupt_report["data_quality"]["chief_complaint"] = "Severe chest pain"
        with pytest.raises(AssertionError) as exc_info:
            assert_zero_patient_leakage(corrupt_report)
        assert "forbidden key 'chief_complaint'" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# Challenge 4: Survey Weight Independence
# ═══════════════════════════════════════════════════════════════════════════════

class TestChallenge4SurveyWeightIndependence:
    """
    Stress-tests the evaluator to empirically prove that survey weights (PATWT)
    do NOT alter Wilson confidence intervals, sensitivity, specificity, PPV, NPV,
    or confusion matrix counts.
    """

    def test_wilson_ci_and_confusion_matrix_invariance_under_patwt(self):
        """
        Create 3 identical cohorts of 10 encounters with identical clinical values
        but drastically different PATWT values:
        Cohort A: PATWT = 1.0 for all records.
        Cohort B: PATWT = 10000.0 for all records.
        Cohort C: Randomized wildly varying PATWT (from 0.01 to 999999.0).
        Verify that all calculated evaluation metrics are 100% identical.
        """
        y_ref = np.array([2, 2, 2, 1, 1, 1, 0, 0, 0, 0], dtype=int)
        y_prod = np.array([2, 2, 1, 1, 1, 0, 0, 0, 1, 0], dtype=int)
        y_raw = np.array([2, 1, 1, 1, 1, 0, 0, 0, 0, 0], dtype=int)
        conf = np.array([0.95, 0.90, 0.70, 0.85, 0.88, 0.65, 0.92, 0.99, 0.60, 0.95], dtype=float)
        guardrail = np.array([False, True, False, False, False, False, False, False, False, False], dtype=bool)

        formdatas_base = [
            {"patient_age": 20 + i * 5, "patient_sex": "female" if i % 2 == 0 else "male"}
            for i in range(10)
        ]

        # Cohort A: PATWT = 1.0
        patwts_a = [1.0] * 10
        metrics_a = calculate_evaluation_metrics(
            y_ref=y_ref,
            y_prod=y_prod,
            y_raw=y_raw,
            conf=conf,
            guardrail=guardrail,
            formdatas=formdatas_base,
        )

        # Cohort B: PATWT = 10000.0
        patwts_b = [10000.0] * 10
        metrics_b = calculate_evaluation_metrics(
            y_ref=y_ref,
            y_prod=y_prod,
            y_raw=y_raw,
            conf=conf,
            guardrail=guardrail,
            formdatas=formdatas_base,
        )

        # Cohort C: Wildly varying PATWT
        patwts_c = [0.01, 100.0, 55555.55, 999999.0, 42.0, 1234.56, 88.8, 777.7, 0.5, 50000.0]
        metrics_c = calculate_evaluation_metrics(
            y_ref=y_ref,
            y_prod=y_prod,
            y_raw=y_raw,
            conf=conf,
            guardrail=guardrail,
            formdatas=formdatas_base,
        )

        # 1. Confusion matrices must be identical
        assert metrics_a["confusion_matrix"] == metrics_b["confusion_matrix"]
        assert metrics_a["confusion_matrix"] == metrics_c["confusion_matrix"]

        # 2. Overall agreement must be identical
        assert metrics_a["overall_agreement"] == metrics_b["overall_agreement"]
        assert metrics_a["overall_agreement"] == metrics_c["overall_agreement"]

        # 3. Per-tier discrimination (sensitivity, specificity, PPV, NPV + Wilson CIs) must be identical
        for tier in ["EMERGENCY", "URGENT", "ROUTINE"]:
            disc_a = metrics_a["discrimination"][tier]
            disc_b = metrics_b["discrimination"][tier]
            disc_c = metrics_c["discrimination"][tier]

            assert disc_a["tp"] == disc_b["tp"] == disc_c["tp"]
            assert disc_a["fn"] == disc_b["fn"] == disc_c["fn"]
            assert disc_a["fp"] == disc_b["fp"] == disc_c["fp"]
            assert disc_a["tn"] == disc_b["tn"] == disc_c["tn"]

            assert disc_a["sensitivity"] == disc_b["sensitivity"] == disc_c["sensitivity"]
            assert disc_a["specificity"] == disc_b["specificity"] == disc_c["specificity"]
            assert disc_a["ppv"] == disc_b["ppv"] == disc_c["ppv"]
            assert disc_a["npv"] == disc_b["npv"] == disc_c["npv"]

        # 4. Safety metrics must be identical
        assert metrics_a["safety_metrics"] == metrics_b["safety_metrics"] == metrics_c["safety_metrics"]

        # 5. Guardrail lift must be identical
        assert metrics_a["guardrail_lift"] == metrics_b["guardrail_lift"] == metrics_c["guardrail_lift"]

        # 6. Calibration ECE must be identical
        assert metrics_a["calibration_diagnostic"] == metrics_b["calibration_diagnostic"] == metrics_c["calibration_diagnostic"]

        # 7. Subgroup metrics must be identical
        assert metrics_a["subgroups"] == metrics_b["subgroups"] == metrics_c["subgroups"]


# ═══════════════════════════════════════════════════════════════════════════════
# Challenge 5: Statistical & Mathematical Boundaries (Wilson Interval)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChallenge5StatisticalBoundaries:
    """
    Stress-tests mathematical boundaries of Wilson intervals (n=0, k=0, k=n).
    """

    def test_wilson_boundary_zero_denominator(self):
        """When n=0, wilson returns (nan, nan, nan) and wilson_dict returns None values."""
        p, lo, hi = wilson(0, 0)
        assert math.isnan(p)
        assert math.isnan(lo)
        assert math.isnan(hi)

        wd = wilson_dict(0, 0)
        assert wd["point"] is None
        assert wd["ci_lower"] is None
        assert wd["ci_upper"] is None
        assert wd["formatted"] == "   n/a   "

    def test_wilson_boundary_zero_successes(self):
        """When k=0, n=100, point estimate is 0.0, lower bound >= 0.0."""
        p, lo, hi = wilson(0, 100)
        assert p == 0.0
        assert lo == 0.0
        assert hi > 0.0 and hi < 0.05

    def test_wilson_boundary_all_successes(self):
        """When k=100, n=100, point estimate is 1.0, upper bound is 1.0 (within float precision)."""
        p, lo, hi = wilson(100, 100)
        assert p == 1.0
        assert lo > 0.95 and lo < 1.0
        assert math.isclose(hi, 1.0, rel_tol=1e-9)
        assert hi <= 1.0

        wd = wilson_dict(100, 100)
        assert wd["point"] == 1.0
        assert wd["ci_upper"] == 1.0
