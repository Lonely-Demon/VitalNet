"""
Unit and Integration Tests for Korean KTAS 2019 External Evaluation Adapter (Gate 3A).

Validates:
- Test 1: Standard-library deterministic OpenXML (.xlsx) parsing, formula cell rejection fail-closed,
  and duplicate header detection.
- Test 2: Exact sheet name enforcement ("N=1267 data" and "coding sheet"), rejecting single-sheet or fuzzy fallbacks.
- Test 3: Exact schema header validation: missing Saturation, missing KTAS_expert, and unexpected extra headers fail closed.
- Test 4: Inline strings parsing without xl/sharedStrings.xml.
- Test 5: Official KTAS sex mapping (1 = Female, 2 = Male) regression tests against coding sheet definition.
- Test 6: Nonnumeric tokens handling ("#NULL!" and "측불" treated strictly as missing without zero coercion).
- Test 7: Site-stratified 5-vital completeness analysis (Local ED 0% complete due to 100% missing saturation;
  Regional ED containing 100% of complete 5-vital cohort).
- Test 8: Unified physiological plausibility bounds (allowing low saturation down to 20.0, handling out-of-bounds
  vitals and blood pressure inversion with exclusion counters).
- Test 9: Strict isolation and zero in-memory materialization of raw rows or prohibited fields.
- Test 10: Deterministic bilingual symptom parser (Hangul and English) with negation handling.
- Test 11: Gate 3A scoring refusal by default (raises EvaluationRefusedError; exit code 2 on CLI;
  no JSON artifact created; unlocked with gate_3a_scoring_authorized).
- Test 12: CLI inspection and evaluation E2E execution with aggregate JSON reporting.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import xml.etree.ElementTree as ET
import zipfile

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
    ARM_KTAS_PRIMARY,
    ARM_KTAS_VITAL_ONLY,
    EXACT_KTAS_REFUSAL_MESSAGE,
    EXPECTED_DATA_HEADERS,
    KTAS_PARSER_VERSION,
    KTAS_PROHIBITED_FIELDS,
    KTAS_V1,
    AggregateDataQuality,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    KTAS2019Source,
    StreamingKTASSymptomCoverageAccumulator,
    compute_file_sha256,
    compute_ktas_symptom_parser_coverage,
    get_evaluation_source,
    parse_ktas_symptoms,
)
from evaluation_sources.ktas_2019 import (
    _col2idx,
    _map_sex,
    _read_ktas_xlsx_sheets,
    _safe_float,
    _safe_int,
    check_vital_plausibility,
    EXPECTED_DATA_SHEET_NAME,
    EXPECTED_CODING_SHEET_NAME,
)
from evaluate_on_real import (
    assert_zero_patient_leakage,
    build_inspection_json_report,
    run_evaluation,
    run_inspection,
)


# ── Synthetic XLSX Generation Helper (Standard Library Only) ─────────────────

def _get_col_letter(col_idx: int) -> str:
    """Converts 0-based column index to Excel column string (e.g. 0 -> 'A', 25 -> 'Z', 26 -> 'AA')."""
    res = ""
    col_idx += 1
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        res = chr(ord("A") + rem) + res
    return res


def create_synthetic_xlsx_bytes(
    sheet_name: str,
    rows: List[List[Any]],
    include_formula_at: Optional[Tuple[int, int]] = None,
    use_inline_strings: bool = False,
) -> bytes:
    """
    Creates a valid or intentionally malformed in-memory .xlsx ZIP archive for synthetic testing.
    Supports both shared strings and inline strings (<is><t>...</t></is>).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        sst_override = (
            '\n  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            if not use_inline_strings
            else ""
        )
        zf.writestr(
            "[Content_Types].xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>{sst_override}
</Types>""",
        )

        # _rels/.rels
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )

        # xl/workbook.xml
        zf.writestr(
            "xl/workbook.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )

        # xl/_rels/workbook.xml.rels
        sst_rel = (
            '\n  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            if not use_inline_strings
            else ""
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>{sst_rel}
</Relationships>""",
        )

        # Worksheet rows and strings
        shared_strings: List[str] = []
        string_to_idx: Dict[str, int] = {}

        rows_xml: List[str] = []
        for r_idx, row in enumerate(rows, start=1):
            cells_xml: List[str] = []
            for c_idx, val in enumerate(row):
                col_letter = _get_col_letter(c_idx)
                cell_ref = f"{col_letter}{r_idx}"

                if include_formula_at and include_formula_at == (r_idx, c_idx):
                    cells_xml.append(f'<c r="{cell_ref}"><f>SUM(A1:B1)</f><v>100</v></c>')
                    continue

                if val is None:
                    continue

                s_val = str(val)
                if s_val == "#NULL!":
                    cells_xml.append(f'<c r="{cell_ref}" t="e"><v>#NULL!</v></c>')
                elif s_val != "측불" and _is_pure_number(s_val):
                    cells_xml.append(f'<c r="{cell_ref}"><v>{s_val}</v></c>')
                else:
                    if use_inline_strings:
                        escaped = s_val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        cells_xml.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{escaped}</t></is></c>')
                    else:
                        if s_val not in string_to_idx:
                            string_to_idx[s_val] = len(shared_strings)
                            shared_strings.append(s_val)
                        idx = string_to_idx[s_val]
                        cells_xml.append(f'<c r="{cell_ref}" t="s"><v>{idx}</v></c>')

            rows_xml.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

        if not use_inline_strings:
            sst_xml = [
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">',
            ]
            for s in shared_strings:
                escaped = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                sst_xml.append(f"<si><t>{escaped}</t></si>")
            sst_xml.append("</sst>")
            zf.writestr("xl/sharedStrings.xml", "".join(sst_xml))

        ws_xml = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>',
            "".join(rows_xml),
            "</sheetData></worksheet>",
        ]
        zf.writestr("xl/worksheets/sheet1.xml", "".join(ws_xml))

    buf.seek(0)
    return buf.getvalue()


def _is_pure_number(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


# ── Synthetic Fixture Rows ───────────────────────────────────────────────────

SYNTHETIC_KTAS_HEADERS = list(EXPECTED_DATA_HEADERS)

# 10 synthetic patient rows covering all required test edge cases:
# - row 0: Local ED (Group 1), adult female (Sex=1), KTAS_expert 1 (EMERGENCY), complete except missing Saturation ("측불")
# - row 1: Regional ED (Group 2), adult male (Sex=2), KTAS_expert 2 (EMERGENCY), all 5 vitals complete
# - row 2: Regional ED (Group 2), elderly female (Sex=1), KTAS_expert 3 (URGENT), all 5 vitals complete
# - row 3: Regional ED (Group 2), child male (Sex=2, decimal age 4.7), KTAS_expert 4 (ROUTINE), all 5 vitals complete
# - row 4: Regional ED (Group 2), young adult female (Sex=1), KTAS_expert 5 (ROUTINE), all 5 vitals complete
# - row 5: Local ED (Group 1), adult male (Sex=2), KTAS_expert 3 (URGENT), missing Saturation (None)
# - row 6: Regional ED (Group 2), adult female (Sex=1), KTAS_expert 2, missing DBP only (shows incomplete 5-vitals)
# - row 7: Regional ED (Group 2), adult male (Sex=2), KTAS_expert 1, inverted BP (SBP 80 <= DBP 90)
# - row 8: Regional ED (Group 2), adult female (Sex=1), invalid KTAS_expert 9, complete vitals
# - row 9: Local ED (Group 1), adult female (Sex=1), KTAS_expert 3, NRS_pain "#NULL!", Saturation "측불"
SYNTHETIC_KTAS_DATA_ROWS = [
    # 0: Group 1, Sex 1 (Female), KTAS 1, missing sat (측불)
    [1, 1, 45, 1, 2, "가슴 통증", 1, 1, 8, 120, 80, 85, 18, 36.5, "측불", 2, "Angina", 2, 1, 0, 120, 5, 0],
    # 1: Group 2, Sex 2 (Male), KTAS 2, complete 5 vitals
    [2, 2, 62, 1, 2, "호흡 곤란", 1, 1, 7, 140, 90, 110, 24, 37.8, 92, 2, "Pneumonia", 2, 2, 0, 180, 8, 0],
    # 2: Group 2, Sex 1 (Female), KTAS 3, complete 5 vitals
    [2, 1, 75, 2, 2, "복통", 1, 1, 5, 130, 85, 78, 16, 36.8, 98, 3, "Gastritis", 1, 3, 0, 90, 4, 0],
    # 3: Group 2, Sex 2 (Male), KTAS 4, decimal age 4.7, complete 5 vitals
    [2, 2, 4.7, 2, 1, "발열", 1, 1, 3, 100, 60, 95, 20, 38.5, 99, 4, "URI", 1, 4, 0, 45, 3, 0],
    # 4: Group 2, Sex 1 (Female), KTAS 5, complete 5 vitals
    [2, 1, 22, 2, 1, "찰과상", 1, 2, 0, 115, 75, 72, 14, 36.4, 100, 5, "Abrasion", 1, 5, 0, 30, 2, 0],
    # 5: Group 1, Sex 2 (Male), KTAS 3, missing sat (None)
    [1, 2, 38, 2, 2, "두통", 1, 1, 4, 125, 82, 80, 18, 36.7, None, 3, "Migraine", 1, 3, 0, 60, 5, 0],
    # 6: Group 2, Sex 1 (Female), KTAS 2, missing DBP only
    [2, 1, 50, 1, 2, "어지러움", 1, 1, 6, 110, None, 90, 18, 36.6, 96, 2, "Vertigo", 1, 2, 0, 75, 4, 0],
    # 7: Group 2, Sex 2 (Male), KTAS 1, inverted BP (SBP 80 <= DBP 90)
    [2, 2, 70, 1, 2, "쇼크 의심", 3, 2, 0, 80, 90, 125, 28, 35.8, 88, 1, "Septic shock", 3, 1, 0, 240, 10, 0],
    # 8: Group 2, Sex 1 (Female), invalid KTAS 9
    [2, 1, 30, 2, 2, "불안", 1, 2, 0, 120, 80, 70, 16, 36.5, 98, 4, "Anxiety", 1, 9, 0, 40, 3, 0],
    # 9: Group 1, Sex 1 (Female), KTAS 3, NRS_pain #NULL!, sat 측불
    [1, 1, 55, 2, 2, "요통", 1, 1, "#NULL!", 135, 88, 76, 16, 36.9, "측불", 3, "Lumbago", 1, 3, 0, 80, 4, 0],
]

SYNTHETIC_CODING_HEADERS = ["Variable", "Description", "Coding"]
SYNTHETIC_CODING_ROWS = [
    ["Group", "Hospital group", "1=Local ED, 2=Regional ED"],
    ["Sex", "Gender", "1: Female / 2: Male"],
    ["Age", "Patient age in years", "Numeric"],
    ["Arrival mode", "Mode of arrival", "1=119, 2=Other"],
    ["Injury", "Injury status", "1=Injury, 2=Non-injury"],
    ["Chief_complain", "Chief complaint", "Free text"],
    ["Mental", "Mental status", "1=Alert, 2=Verbal, 3=Pain, 4=Unresponsive"],
    ["Pain", "Pain presence", "1=Yes, 2=No"],
    ["NRS_pain", "NRS pain score", "0-10, #NULL!=Missing"],
    ["SBP", "Systolic BP (mmHg)", "Numeric, 측불=Unavailable"],
    ["DBP", "Diastolic BP (mmHg)", "Numeric, 측불=Unavailable"],
    ["HR", "Heart rate (bpm)", "Numeric, 측불=Unavailable"],
    ["RR", "Respiratory rate", "Numeric, 측불=Unavailable"],
    ["BT", "Body temperature (C)", "Numeric, 측불=Unavailable"],
    ["Saturation", "Oxygen saturation (%)", "Numeric, 측불=Unavailable"],
    ["KTAS_RN", "Nurse triage score", "1 to 5"],
    ["Diagnosis in ED", "Emergency diagnosis", "Text/Code"],
    ["Disposition", "Patient disposition", "1=Discharge, 2=Ward, 3=ICU, 4=Transfer, 5=Death"],
    ["KTAS_expert", "Expert triage score", "1 to 5"],
    ["Error_group", "Mistriage error type", "0=None, 1=Under, 2=Over"],
    ["Length of stay_min", "Length of stay in minutes", "Numeric"],
    ["KTAS duration_min", "Triage duration in minutes", "Numeric"],
    ["mistriage", "Mistriage flag", "0=Correct, 1=Mistriaged"],
]


# ── Pytest Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_ktas_data_xlsx(tmp_path: Any) -> str:
    rows = [SYNTHETIC_KTAS_HEADERS] + SYNTHETIC_KTAS_DATA_ROWS
    content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows)
    path = os.path.join(str(tmp_path), "synthetic_ktas_data.xlsx")
    with open(path, "wb") as f:
        f.write(content)
    return path


@pytest.fixture
def synthetic_ktas_coding_xlsx(tmp_path: Any) -> str:
    rows = [SYNTHETIC_CODING_HEADERS] + SYNTHETIC_CODING_ROWS
    content = create_synthetic_xlsx_bytes(EXPECTED_CODING_SHEET_NAME, rows)
    path = os.path.join(str(tmp_path), "synthetic_ktas_coding.xlsx")
    with open(path, "wb") as f:
        f.write(content)
    return path


# ── Test Suite 1: Fail-Closed XLSX Parsing & Schema Validation ───────────────

class TestKTASXLSXParser:
    """Validates the standard-library deterministic XLSX parser implementation and exact schema validation."""

    def test_col2idx_conversion(self):
        assert _col2idx("A") == 0
        assert _col2idx("Z") == 25
        assert _col2idx("AA") == 26
        assert _col2idx("XFD") == 16383
        with pytest.raises(ValueError, match="Invalid column letter"):
            _col2idx("A1")

    def test_read_valid_sheets(self, synthetic_ktas_data_xlsx: str):
        sheets = _read_ktas_xlsx_sheets(synthetic_ktas_data_xlsx)
        assert EXPECTED_DATA_SHEET_NAME in sheets
        rows = sheets[EXPECTED_DATA_SHEET_NAME]
        assert len(rows) == 11  # 1 header + 10 data rows
        assert rows[0][0] == "Group"
        assert rows[0][2] == "Age"

    def test_corrupted_archive_rejected(self, tmp_path: Any):
        corrupt_path = os.path.join(str(tmp_path), "corrupt.xlsx")
        with open(corrupt_path, "wb") as f:
            f.write(b"NOT_A_VALID_ZIP_ARCHIVE")
        with pytest.raises(ValueError, match="Malformed or corrupt XLSX archive"):
            _read_ktas_xlsx_sheets(corrupt_path)

    def test_formula_cells_fail_closed(self, tmp_path: Any):
        rows = [SYNTHETIC_KTAS_HEADERS] + SYNTHETIC_KTAS_DATA_ROWS
        content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows, include_formula_at=(2, 3))
        path = os.path.join(str(tmp_path), "formula.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        with pytest.raises(ValueError, match="Formula cells are unsupported"):
            _read_ktas_xlsx_sheets(path)

    def test_duplicate_headers_rejected(self, tmp_path: Any):
        bad_headers = list(SYNTHETIC_KTAS_HEADERS)
        bad_headers[1] = bad_headers[0]  # Duplicate 'Group' header
        rows = [bad_headers] + SYNTHETIC_KTAS_DATA_ROWS
        content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows)
        path = os.path.join(str(tmp_path), "dup_headers.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        source = KTAS2019Source(file_path=path)
        with pytest.raises(ValueError, match="Duplicate header 'Group' detected"):
            source.inspect()

    def test_unexpected_data_sheet_name_rejected_fail_closed(self, tmp_path: Any):
        rows = [SYNTHETIC_KTAS_HEADERS] + SYNTHETIC_KTAS_DATA_ROWS
        content = create_synthetic_xlsx_bytes("Sheet1", rows)
        path = os.path.join(str(tmp_path), "wrong_sheet.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        source = KTAS2019Source(file_path=path)
        with pytest.raises(ValueError, match=f"Expected data worksheet '{EXPECTED_DATA_SHEET_NAME}' not found"):
            source.inspect()

    def test_unexpected_coding_sheet_name_rejected_fail_closed(
        self, synthetic_ktas_data_xlsx: str, tmp_path: Any
    ):
        rows = [SYNTHETIC_CODING_HEADERS] + SYNTHETIC_CODING_ROWS
        content = create_synthetic_xlsx_bytes("Definitions", rows)
        path = os.path.join(str(tmp_path), "wrong_coding_sheet.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            coding_file_path=path,
        )
        with pytest.raises(ValueError, match=f"Expected coding worksheet '{EXPECTED_CODING_SHEET_NAME}' not found"):
            source.inspect()

    def test_missing_saturation_header_rejected_fail_closed(self, tmp_path: Any):
        bad_headers = [h for h in SYNTHETIC_KTAS_HEADERS if h != "Saturation"]
        bad_rows = [[r[c_idx] for c_idx, h in enumerate(SYNTHETIC_KTAS_HEADERS) if h != "Saturation"] for r in SYNTHETIC_KTAS_DATA_ROWS]
        rows = [bad_headers] + bad_rows
        content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows)
        path = os.path.join(str(tmp_path), "missing_sat_header.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        source = KTAS2019Source(file_path=path)
        with pytest.raises(ValueError, match="Missing required headers.*Saturation"):
            source.inspect()

    def test_missing_ktas_expert_header_rejected_fail_closed(self, tmp_path: Any):
        bad_headers = [h for h in SYNTHETIC_KTAS_HEADERS if h != "KTAS_expert"]
        bad_rows = [[r[c_idx] for c_idx, h in enumerate(SYNTHETIC_KTAS_HEADERS) if h != "KTAS_expert"] for r in SYNTHETIC_KTAS_DATA_ROWS]
        rows = [bad_headers] + bad_rows
        content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows)
        path = os.path.join(str(tmp_path), "missing_expert_header.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        source = KTAS2019Source(file_path=path)
        with pytest.raises(ValueError, match="Missing required headers.*KTAS_expert"):
            source.inspect()

    def test_unexpected_extra_header_rejected_fail_closed(self, tmp_path: Any):
        bad_headers = list(SYNTHETIC_KTAS_HEADERS) + ["Patient_SSN"]
        bad_rows = [r + ["999-99-9999"] for r in SYNTHETIC_KTAS_DATA_ROWS]
        rows = [bad_headers] + bad_rows
        content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows)
        path = os.path.join(str(tmp_path), "extra_header.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        source = KTAS2019Source(file_path=path)
        with pytest.raises(ValueError, match="Unexpected extra headers.*Patient_SSN"):
            source.inspect()

    def test_inline_strings_without_shared_strings_xml(self, tmp_path: Any):
        rows = [SYNTHETIC_KTAS_HEADERS] + SYNTHETIC_KTAS_DATA_ROWS
        content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows, use_inline_strings=True)
        path = os.path.join(str(tmp_path), "inline_strings.xlsx")
        with open(path, "wb") as f:
            f.write(content)

        # Verify that zip archive contains no xl/sharedStrings.xml
        with zipfile.ZipFile(path, "r") as zf:
            assert "xl/sharedStrings.xml" not in zf.namelist()

        # Verify adapter parses inline strings correctly
        source = KTAS2019Source(file_path=path)
        dq = source.inspect()
        assert dq.total_records_inspected == 10
        assert dq.complete_vitals_count == 5


# ── Test Suite 2: Sex Mapping & Demographic Regression ───────────────────────

class TestKTASSexMapping:
    """Validates the official KTAS coding sheet definition (1 = Female, 2 = Male)."""

    def test_official_sex_coding_mapping(self):
        # Official KTAS definition: 1 = Female, 2 = Male
        assert _map_sex(1) == "female"
        assert _map_sex("1") == "female"
        assert _map_sex(1.0) == "female"
        assert _map_sex("female") == "female"
        assert _map_sex("여") == "female"
        assert _map_sex("여자") == "female"
        assert _map_sex("여성") == "female"

        assert _map_sex(2) == "male"
        assert _map_sex("2") == "male"
        assert _map_sex(2.0) == "male"
        assert _map_sex("male") == "male"
        assert _map_sex("남") == "male"
        assert _map_sex("남자") == "male"
        assert _map_sex("남성") == "male"

        assert _map_sex(None) == "other"
        assert _map_sex("") == "other"
        assert _map_sex("unknown") == "other"
        assert _map_sex(9) == "other"


# ── Test Suite 3: Inspection, Site Stratification & Unified Plausibility ────

class TestKTASInspectionAndSiteStratification:
    """Validates aggregate inspection, site completeness, nonnumeric tokens, and unified plausibility."""

    def test_aggregate_inspection_metrics(
        self, synthetic_ktas_data_xlsx: str, synthetic_ktas_coding_xlsx: str
    ):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            coding_file_path=synthetic_ktas_coding_xlsx,
        )
        dq = source.inspect()

        assert isinstance(dq, AggregateDataQuality)
        assert dq.total_records_inspected == 10
        assert len(dq.headers_present) == 23
        assert "KTAS_expert" in dq.headers_present

        # Both hashes tracked
        assert dq.source_manifest.file_sha256 is not None
        assert "coding_sheet_provenance" in dq.extra_metadata
        coding_prov = dq.extra_metadata["coding_sheet_provenance"]
        assert coding_prov["status"] == "loaded"
        assert coding_prov["coding_file_sha256"] is not None

        # Zero raw patient leakage
        report = build_inspection_json_report(dq)
        assert_zero_patient_leakage(report)

    def test_site_stratified_completeness_and_regional_confinement(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(file_path=synthetic_ktas_data_xlsx)
        dq = source.inspect()

        extra = dq.extra_metadata
        assert "site_stratified_completeness" in extra
        site_strat = extra["site_stratified_completeness"]

        # Local ED (Group 1) has 3 encounters, 0 complete 5-vitals (due to missing saturation)
        local_ed = site_strat["local_ed_group_1"]
        assert local_ed["total_records"] == 3
        assert local_ed["complete_5_vitals_count"] == 0
        assert local_ed["saturation_missing_count"] == 3

        # Regional ED (Group 2) has 7 encounters; 5 have complete 5-vitals (rows 1, 2, 3, 4, 8)
        regional_ed = site_strat["regional_ed_group_2"]
        assert regional_ed["total_records"] == 7
        assert regional_ed["complete_5_vitals_count"] == 5
        assert regional_ed["saturation_missing_count"] == 0

        # Overall complete vitals
        assert dq.complete_vitals_count == 5
        assert dq.complete_vitals_pct == 50.0

    def test_nonnumeric_tokens_측불_and_null_treated_as_missing(self):
        assert _safe_float("#NULL!") is None
        assert _safe_float("측불") is None
        assert _safe_float("None") is None
        assert _safe_float("null") is None
        assert _safe_float("") is None
        assert _safe_float(None) is None
        assert _safe_float("36.5") == 36.5

        assert _safe_int("#NULL!") is None
        assert _safe_int("측불") is None
        assert _safe_int("4.7") == 5

    def test_unified_plausibility_bounds_and_exclusion_reasons(self):
        # 1. Severe low saturation (down to 20.0) is physiologically valid in severe hypoxia / arrest
        sanitized, is_comp, reason = check_vital_plausibility(37.0, 110.0, 120.0, 80.0, 20.0)
        assert is_comp is True
        assert sanitized["Saturation"] == 20.0
        assert reason is None

        # 2. Implausible temperature (e.g. 50.0 C) rejected and reason recorded
        sanitized, is_comp, reason = check_vital_plausibility(50.0, 80.0, 120.0, 80.0, 98.0)
        assert is_comp is False
        assert sanitized["BT"] is None
        assert reason == "implausible_bt_value_50.0"

        # 3. Blood pressure inversion (SBP <= DBP) rejected and reason recorded
        sanitized, is_comp, reason = check_vital_plausibility(36.5, 80.0, 80.0, 90.0, 98.0)
        assert is_comp is False
        assert sanitized["SBP"] is None
        assert sanitized["DBP"] is None
        assert reason == "blood_pressure_inversion"

    def test_expert_vs_nurse_acuity_distribution_separation(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(file_path=synthetic_ktas_data_xlsx)
        dq = source.inspect()

        extra = dq.extra_metadata
        assert "nurse_vs_expert_distribution" in extra
        dist = extra["nurse_vs_expert_distribution"]

        expert_counts = dist["ktas_expert_levels_1_to_5"]
        assert expert_counts["1"] == 2
        assert expert_counts["2"] == 2
        assert expert_counts["3"] == 3
        assert expert_counts["4"] == 1
        assert expert_counts["5"] == 1
        assert expert_counts["other"] == 1  # Row 8 with invalid KTAS 9

        nurse_counts = dist["ktas_rn_levels_1_to_5_audit_only"]
        assert isinstance(nurse_counts, dict)
        assert sum(nurse_counts.values()) == 10


# ── Test Suite 4: Gate 3A Governance & Zero In-Memory Raw Retention ─────────

class TestKTASGate3AGovernanceAndScoring:
    """Validates Gate 3A scoring refusal, zero raw memory retention, and input contracts."""

    def test_default_evaluation_refused_without_authorization(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(file_path=synthetic_ktas_data_xlsx)
        with pytest.raises(EvaluationRefusedError, match="Korean KTAS 2019 model scoring is locked"):
            source.load_for_evaluation()

    def test_evaluation_loads_when_authorized(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            gate_3a_scoring_authorized=True,
        )
        records, counters, manifest = source.load_for_evaluation()

        assert manifest.scoring_supported is True
        assert len(records) == 9  # 1 excluded due to invalid KTAS_expert 9 (row 8)
        assert counters.reasons.get("invalid_or_missing_ktas_expert_label") == 1
        assert counters.reasons.get("blood_pressure_inversion") == 1

        # Check demographic mappings (Row 0 has Sex=1 -> female; Row 1 has Sex=2 -> male)
        assert records[0].form_data["patient_sex"] == "female"
        assert records[1].form_data["patient_sex"] == "male"

    def test_input_mode_isolation_and_partial_arm(
        self, synthetic_ktas_data_xlsx: str
    ):
        # 1. Primary arm (ktas_triage_contract_v1)
        source_primary = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            input_mode=ARM_KTAS_PRIMARY,
            gate_3a_scoring_authorized=True,
        )
        records_primary, _, _ = source_primary.load_for_evaluation()
        for r in records_primary:
            assert isinstance(r.form_data["symptoms"], list)
            assert r.form_data["chief_complaint"] == ""
            assert r.is_partial_input is False

        # 2. Vital-only partial-input stress-test arm (ktas_vital_only_partial_v1)
        source_vital_only = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            input_mode=ARM_KTAS_VITAL_ONLY,
            gate_3a_scoring_authorized=True,
        )
        records_vo, _, _ = source_vital_only.load_for_evaluation()
        for r in records_vo:
            assert r.form_data["symptoms"] == []
            assert r.form_data["chief_complaint"] == ""
            assert r.is_partial_input is True

    def test_prohibited_fields_stripped_and_zero_raw_complaint_retention(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            gate_3a_scoring_authorized=True,
        )
        records, _, _ = source.load_for_evaluation()

        for r in records:
            form = r.form_data
            raw = r.raw_fields

            # Prohibited fields never in form_data or raw_fields
            for prohibited in KTAS_PROHIBITED_FIELDS:
                assert prohibited not in form
                assert prohibited.lower().replace(" ", "_") not in form
                assert prohibited not in raw

            # Raw free text complaint never retained
            assert "Chief_complain" not in form
            assert "Chief_complain" not in raw
            assert form.get("chief_complaint") == ""
            assert raw == {}


# ── Test Suite 5: Bilingual Symptom Parser & Negation Handling ───────────────

class TestKTASSymptomParser:
    """Validates the deterministic bilingual symptom parser for Korean KTAS chief complaints."""

    def test_korean_symptom_parsing_accuracy(self):
        cases = [
            ("가슴 통증 및 흉통", ["chest_pain"]),
            ("숨이 차고 호흡 곤란", ["breathlessness"]),
            ("의식 저하 및 실신", ["altered_consciousness"]),
            ("대량 출혈 및 토혈", ["severe_bleeding"]),
            ("전신 경련 및 발작", ["seizure"]),
            ("고열 및 발열", ["high_fever"]),
            ("심한 복통 및 배 아픔", ["severe_abdominal_pain"]),
            ("지속적 구토 및 오심", ["persistent_vomiting"]),
            ("극심한 두통", ["severe_headache"]),
            ("우측 편마비 및 편측 약화", ["weakness_one_side"]),
            ("말 어눌 및 언어 장애", ["difficulty_speaking"]),
            ("얼굴 부종 및 안면 부종", ["swelling_face_throat"]),
        ]
        for text, expected in cases:
            parsed = parse_ktas_symptoms(text)
            assert parsed == expected, f"Failed for text: '{text}', expected {expected}, got {parsed}"

    def test_english_symptom_parsing_accuracy(self):
        cases = [
            ("Severe chest pain radiating to arm", ["chest_pain"]),
            ("Shortness of breath and wheezing", ["breathlessness"]),
            ("Syncope and altered mental status", ["altered_consciousness"]),
            ("Massive GI bleed", ["severe_bleeding"]),
            ("Status epilepticus with seizures", ["seizure"]),
            ("High fever with chills", ["high_fever"]),
            ("Acute abdominal pain and flank pain", ["severe_abdominal_pain"]),
            ("Persistent vomiting and emesis", ["persistent_vomiting"]),
            ("Migraine and severe headache", ["severe_headache"]),
            ("Facial droop and unilateral weakness", ["weakness_one_side"]),
            ("Dysarthria and slurred speech", ["difficulty_speaking"]),
            ("Anaphylaxis with throat swelling", ["swelling_face_throat"]),
        ]
        for text, expected in cases:
            parsed = parse_ktas_symptoms(text)
            assert parsed == expected, f"Failed for English text: '{text}'"

    def test_negation_handling(self):
        negated_cases = [
            "두통 없음",
            "발열 없음",
            "복통 부정",
            "가슴 통증 없음",
            "no fever",
            "denies chest pain",
            "without headache",
        ]
        for text in negated_cases:
            parsed = parse_ktas_symptoms(text)
            assert parsed == [], f"Expected negation to yield empty list for '{text}', got {parsed}"

    def test_empty_and_unmapped_complaints(self):
        assert parse_ktas_symptoms("") == []
        assert parse_ktas_symptoms(None) == []
        assert parse_ktas_symptoms("측불") == []
        assert parse_ktas_symptoms("#NULL!") == []
        assert parse_ktas_symptoms("단순 찰과상") == []
        assert parse_ktas_symptoms("드레싱 교환") == []

    def test_streaming_coverage_accumulator_zero_raw_retention(self):
        acc = StreamingKTASSymptomCoverageAccumulator()
        complaints = ["가슴 통증", "호흡 곤란", "단순 찰과상", "두통 없음", ""]
        for c in complaints:
            acc.update(c)

        coverage = acc.finalize()
        assert coverage["parser_version"] == KTAS_PARSER_VERSION
        assert coverage["total_complaints_inspected"] == 5
        assert coverage["non_empty_complaints_count"] == 4
        assert coverage["complaints_with_mapped_symptoms_count"] == 2
        assert coverage["symptom_frequency_distribution"]["chest_pain"] == 1
        assert coverage["symptom_frequency_distribution"]["breathlessness"] == 1

        # Strict zero-leakage: raw complaints are never stored in accumulator
        assert not hasattr(acc, "complaints")
        assert not hasattr(acc, "raw_records")
        for k, v in acc.__dict__.items():
            assert not any(c in str(v) for c in ["가슴 통증", "호흡 곤란"] if c)


# ── Test Suite 6: CLI Execution & Zero Patient Data Leakage ──────────────────

class TestKTASCLIE2EAndZeroLeakage:
    """Validates CLI integration, report format, zero leakage, and refusal."""

    def test_cli_ktas_inspection_json_report_e2e(
        self, synthetic_ktas_data_xlsx: str, synthetic_ktas_coding_xlsx: str, tmp_path: Any
    ):
        json_out = os.path.join(str(tmp_path), "ktas_inspection.json")
        cmd = [
            sys.executable,
            os.path.join(TOOLS_DIR, "evaluate_on_real.py"),
            "--inspect-source",
            "ktas-2019",
            "--file",
            synthetic_ktas_data_xlsx,
            "--coding-file",
            synthetic_ktas_coding_xlsx,
            "--json-out",
            json_out,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert res.returncode == 0, f"CLI inspection failed: {res.stderr}"

        assert os.path.isfile(json_out)
        with open(json_out, "r", encoding="utf-8") as f:
            report = json.load(f)

        # Zero patient data leakage validation
        assert_zero_patient_leakage(report)

        # Structure checks
        assert report["execution_mode"] == "inspection"
        assert report["source_manifest"]["source_id"] == "ktas_2019"
        assert report["data_quality"]["total_records_inspected"] == 10
        assert report["data_quality"]["complete_vitals_count"] == 5
        assert report["data_quality"]["extra_metadata"]["coding_sheet_provenance"]["status"] == "loaded"

    def test_cli_ktas_evaluation_refused_by_default(
        self, synthetic_ktas_data_xlsx: str, tmp_path: Any
    ):
        json_out = os.path.join(str(tmp_path), "ktas_eval.json")
        cmd = [
            sys.executable,
            os.path.join(TOOLS_DIR, "evaluate_on_real.py"),
            "--evaluate-source",
            "ktas-2019",
            "--file",
            synthetic_ktas_data_xlsx,
            "--json-out",
            json_out,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert res.returncode == 2, f"Expected exit code 2 on refusal, got {res.returncode}"
        assert "Korean KTAS 2019 model scoring is locked under Gate 3A governance" in res.stderr
        assert not os.path.exists(json_out)

    def test_missing_dbp_only_fails_5_vital_completeness(self, tmp_path: Any):
        row = [2, 1, 45, 1, 2, "흉통", 1, 1, 5, 120, None, 80, 16, 36.5, 98, 2, "CAD", 1, 2, 0, 60, 5, 0]
        rows = [SYNTHETIC_KTAS_HEADERS, row]
        content = create_synthetic_xlsx_bytes(EXPECTED_DATA_SHEET_NAME, rows)
        path = os.path.join(str(tmp_path), "missing_dbp.xlsx")
        with open(path, "wb") as f:
            f.write(content)

        source = KTAS2019Source(file_path=path)
        dq = source.inspect()
        assert dq.total_records_inspected == 1
        assert dq.complete_vitals_count == 0
        assert dq.complete_vitals_pct == 0.0

    def test_raw_complaints_never_in_reports_or_records(
        self, synthetic_ktas_data_xlsx: str, synthetic_ktas_coding_xlsx: str, tmp_path: Any
    ):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            coding_file_path=synthetic_ktas_coding_xlsx,
            gate_3a_scoring_authorized=True,
        )
        records, _, _ = source.load_for_evaluation()
        dq = source.inspect()
        report = build_inspection_json_report(dq)
        report_str = json.dumps(report, ensure_ascii=False)

        # Raw Korean complaint strings from synthetic fixture
        korean_complaints = ["가슴 통증", "호흡 곤란", "복통", "발열", "찰과상", "두통", "어지러움", "쇼크 의심", "불안", "요통"]
        for kc in korean_complaints:
            # 1. Not in any canonical form_data
            for r in records:
                assert kc not in str(r.form_data)
                assert kc not in str(r.raw_fields)
            # 2. Not in JSON inspection report
            assert kc not in report_str
