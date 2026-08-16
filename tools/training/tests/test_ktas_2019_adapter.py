"""
Comprehensive Synthetic Test Suite for Korean KTAS 2019 Evaluation Source (Gate 3A).

Validates:
- Test 1: Fail-closed deterministic standard-library XLSX parsing (shared strings, error tokens,
  Korean nonnumeric tokens, sparse cells, corrupt archives, formulas, duplicate headers).
- Test 2: Multi-field schema inspection (24 columns, field missingness, numeric distributions,
  Celsius BT preservation, decimal age nearest-integer rounding).
- Test 3: Coding sheet provenance parsing and isolation (never treated as patient encounters).
- Test 4: Five-level KTAS expert acuity distribution & pre-registered ktas_v1 mapping
  (1-2 EMERGENCY, 3 URGENT, 4-5 ROUTINE).
- Test 5: Nurse-label (KTAS_RN) audit-only separation vs expert reference candidate (KTAS_expert).
- Test 6: Five-vital completeness contract (requires BT, HR, SBP, DBP, Saturation; DBP or Saturation
  missing alone marks encounter as incomplete; SBP <= DBP inversion handling).
- Test 7: Conservative nonnumeric token handling ("#NULL!" and "측불" treated as missing, never 0).
- Test 8: Site-stratified completeness logic (Local ED vs Regional ED; saturation missingness).
- Test 9: Strict zero-leakage assertions (prohibited outcome/audit fields and raw free-text
  complaints never enter form_data, raw_fields, exceptions, logs, or JSON reports).
- Test 10: Gate 3A staged scoring refusal by default (raises EvaluationRefusedError, exit code 2,
  no JSON artifact created; unlocked with gate_3a_scoring_authorized).
- Test 11: CLI inspection and evaluation E2E execution with aggregate JSON reporting.
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
from evaluation_sources.ktas_2019 import _col2idx, _read_ktas_xlsx_sheets, _safe_float, _safe_int
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
) -> bytes:
    """
    Creates a valid or intentionally malformed in-memory .xlsx ZIP archive for synthetic testing.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
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
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""",
        )

        # Shared strings and worksheet rows
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
                    if s_val not in string_to_idx:
                        string_to_idx[s_val] = len(shared_strings)
                        shared_strings.append(s_val)
                    idx = string_to_idx[s_val]
                    cells_xml.append(f'<c r="{cell_ref}" t="s"><v>{idx}</v></c>')

            rows_xml.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

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
# - row 0: Local ED (Group 1), adult male, KTAS_expert 1 (EMERGENCY), complete except missing Saturation ("측불")
# - row 1: Regional ED (Group 2), adult female, KTAS_expert 2 (EMERGENCY), all 5 vitals complete
# - row 2: Regional ED (Group 2), elderly male, KTAS_expert 3 (URGENT), all 5 vitals complete
# - row 3: Regional ED (Group 2), child female (decimal age 4.7), KTAS_expert 4 (ROUTINE), all 5 vitals complete
# - row 4: Regional ED (Group 2), young adult, KTAS_expert 5 (ROUTINE), all 5 vitals complete
# - row 5: Local ED (Group 1), adult female, KTAS_expert 3 (URGENT), missing Saturation (None)
# - row 6: Regional ED (Group 2), adult male, KTAS_expert 2, missing DBP only (shows incomplete 5-vitals)
# - row 7: Regional ED (Group 2), adult male, KTAS_expert 1, inverted BP (SBP 80 <= DBP 90)
# - row 8: Regional ED (Group 2), adult female, invalid KTAS_expert 9, complete vitals
# - row 9: Local ED (Group 1), adult male, KTAS_expert 3, NRS_pain "#NULL!", Saturation "측불"
SYNTHETIC_KTAS_DATA_ROWS = [
    # 0: Group 1, KTAS 1, missing sat (측불)
    [1, 1, 45, 1, 2, "가슴 통증", 1, 1, 8, 120, 80, 85, 18, 36.5, "측불", 2, "Angina", 2, 1, 0, 120, 5, 0],
    # 1: Group 2, KTAS 2, complete 5 vitals
    [2, 2, 62, 1, 2, "호흡 곤란", 1, 1, 7, 140, 90, 110, 24, 37.8, 92, 2, "Pneumonia", 2, 2, 0, 180, 8, 0],
    # 2: Group 2, KTAS 3, complete 5 vitals
    [2, 1, 75, 2, 2, "복통", 1, 1, 5, 130, 85, 78, 16, 36.8, 98, 3, "Gastritis", 1, 3, 0, 90, 4, 0],
    # 3: Group 2, KTAS 4, decimal age 4.7, complete 5 vitals
    [2, 2, 4.7, 2, 1, "발열", 1, 1, 3, 100, 60, 95, 20, 38.5, 99, 4, "URI", 1, 4, 0, 45, 3, 0],
    # 4: Group 2, KTAS 5, complete 5 vitals
    [2, 1, 22, 2, 1, "찰과상", 1, 2, 0, 115, 75, 72, 14, 36.4, 100, 5, "Abrasion", 1, 5, 0, 30, 2, 0],
    # 5: Group 1, KTAS 3, missing sat (None)
    [1, 2, 38, 2, 2, "두통", 1, 1, 4, 125, 82, 80, 18, 36.7, None, 3, "Migraine", 1, 3, 0, 60, 5, 0],
    # 6: Group 2, KTAS 2, missing DBP only
    [2, 1, 50, 1, 2, "어지러움", 1, 1, 6, 110, None, 90, 18, 36.6, 96, 2, "Vertigo", 1, 2, 0, 75, 4, 0],
    # 7: Group 2, KTAS 1, inverted BP (SBP 80 <= DBP 90)
    [2, 2, 70, 1, 2, "쇼크 의심", 3, 2, 0, 80, 90, 125, 28, 35.8, 88, 1, "Septic shock", 3, 1, 0, 240, 10, 0],
    # 8: Group 2, invalid KTAS 9
    [2, 1, 30, 2, 2, "불안", 1, 2, 0, 120, 80, 70, 16, 36.5, 98, 4, "Anxiety", 1, 9, 0, 40, 3, 0],
    # 9: Group 1, KTAS 3, NRS_pain #NULL!, sat 측불
    [1, 1, 55, 2, 2, "요통", 1, 1, "#NULL!", 135, 88, 76, 16, 36.9, "측불", 3, "Lumbago", 1, 3, 0, 80, 4, 0],
]

SYNTHETIC_CODING_HEADERS = ["Variable", "Description", "Coding"]
SYNTHETIC_CODING_ROWS = [
    ["Group", "Hospital group", "1=Local ED, 2=Regional ED"],
    ["Sex", "Gender", "1=Male, 2=Female"],
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
    content = create_synthetic_xlsx_bytes("N=1267 data", rows)
    path = os.path.join(str(tmp_path), "synthetic_ktas_data.xlsx")
    with open(path, "wb") as f:
        f.write(content)
    return path


@pytest.fixture
def synthetic_ktas_coding_xlsx(tmp_path: Any) -> str:
    rows = [SYNTHETIC_CODING_HEADERS] + SYNTHETIC_CODING_ROWS
    content = create_synthetic_xlsx_bytes("coding sheet", rows)
    path = os.path.join(str(tmp_path), "synthetic_ktas_coding.xlsx")
    with open(path, "wb") as f:
        f.write(content)
    return path


# ── Test Suite 1: Fail-Closed XLSX Parsing ───────────────────────────────────

class TestKTASXLSXParser:
    """Validates the standard-library deterministic XLSX parser implementation."""

    def test_col2idx_conversion(self):
        assert _col2idx("A") == 0
        assert _col2idx("Z") == 25
        assert _col2idx("AA") == 26
        assert _col2idx("XFD") == 16383
        with pytest.raises(ValueError, match="Invalid column letter"):
            _col2idx("A1")

    def test_read_valid_sheets(self, synthetic_ktas_data_xlsx: str):
        sheets = _read_ktas_xlsx_sheets(synthetic_ktas_data_xlsx)
        assert "N=1267 data" in sheets
        rows = sheets["N=1267 data"]
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
        content = create_synthetic_xlsx_bytes("N=1267 data", rows, include_formula_at=(2, 3))
        path = os.path.join(str(tmp_path), "formula.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        with pytest.raises(ValueError, match="Formula cells are unsupported"):
            _read_ktas_xlsx_sheets(path)

    def test_duplicate_headers_rejected(self, tmp_path: Any):
        bad_headers = list(SYNTHETIC_KTAS_HEADERS)
        bad_headers[1] = bad_headers[0]  # Duplicate 'Group' header
        rows = [bad_headers] + SYNTHETIC_KTAS_DATA_ROWS
        content = create_synthetic_xlsx_bytes("N=1267 data", rows)
        path = os.path.join(str(tmp_path), "dup_headers.xlsx")
        with open(path, "wb") as f:
            f.write(content)
        source = KTAS2019Source(file_path=path)
        with pytest.raises(ValueError, match="Duplicate header 'Group' detected"):
            source.inspect()

    def test_unexpected_sheet_name_rejected(self, tmp_path: Any):
        rows = [SYNTHETIC_KTAS_HEADERS] + SYNTHETIC_KTAS_DATA_ROWS
        # Two unexpected sheets where neither is 'N=1267 data'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
            zf.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
            zf.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="SheetA" sheetId="1" r:id="rId1"/>
    <sheet name="SheetB" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>""")
            zf.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>""")
            zf.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>')
            zf.writestr("xl/worksheets/sheet2.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>')
        buf.seek(0)
        path = os.path.join(str(tmp_path), "wrong_sheets.xlsx")
        with open(path, "wb") as f:
            f.write(buf.getvalue())
        source = KTAS2019Source(file_path=path)
        with pytest.raises(ValueError, match="Could not find expected data sheet"):
            source.inspect()


# ── Test Suite 2: Data Quality Inspection & Site Stratification ───────────────

class TestKTASInspectionAndSiteStratification:
    """Validates aggregate inspection metrics, site stratification, and coding sheet isolation."""

    def test_aggregate_inspection_metrics(
        self, synthetic_ktas_data_xlsx: str, synthetic_ktas_coding_xlsx: str
    ):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            coding_file_path=synthetic_ktas_coding_xlsx,
        )
        dq: AggregateDataQuality = source.inspect()

        assert dq.total_records_inspected == 10
        assert len(dq.headers_present) == len(EXPECTED_DATA_HEADERS)
        assert "KTAS_expert" in dq.headers_present
        assert "KTAS_RN" in dq.headers_present

        # Provenance checks
        manifest = dq.source_manifest
        assert manifest.source_id == "ktas_2019"
        assert manifest.official_url == "https://doi.org/10.1371/journal.pone.0216972"
        assert "PLOS ONE" in manifest.license_note
        assert manifest.file_sha256 is not None

        # Coding sheet provenance check
        extra = dq.extra_metadata
        assert "coding_sheet_provenance" in extra
        coding_prov = extra["coding_sheet_provenance"]
        assert coding_prov["status"] == "loaded"
        assert coding_prov["total_definitions_documented"] == 23
        assert coding_prov["coding_file_sha256"] is not None

        # Temperature unit check: Celsius preserved, observed mean in [35.0, 39.0]
        bt_dist = dq.vital_distributions.get("BT", {})
        assert bt_dist["valid_count"] == 10
        assert 35.0 <= bt_dist["min"] <= 40.0
        assert 35.0 <= bt_dist["max"] <= 40.0

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
        # _safe_float and _safe_int tests
        assert _safe_float("#NULL!") is None
        assert _safe_float("측불") is None
        assert _safe_float("None") is None
        assert _safe_float("null") is None
        assert _safe_float("") is None
        assert _safe_float(None) is None
        assert _safe_float("36.5") == 36.5

        assert _safe_int("#NULL!") is None
        assert _safe_int("측불") is None
        assert _safe_int(None) is None
        assert _safe_int("4.7") == 5  # Nearest-integer rounding
        assert _safe_int("4.2") == 4
        assert _safe_int(4.7) == 5

    def test_expert_vs_nurse_acuity_distribution_separation(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(file_path=synthetic_ktas_data_xlsx)
        dq = source.inspect()

        extra = dq.extra_metadata
        nurse_vs_expert = extra["nurse_vs_expert_distribution"]

        # Expert: KTAS 1 (2), KTAS 2 (2), KTAS 3 (3), KTAS 4 (1), KTAS 5 (1), invalid 9 (1)
        expert_dist = nurse_vs_expert["ktas_expert_levels_1_to_5"]
        assert expert_dist["1"] == 2
        assert expert_dist["2"] == 2
        assert expert_dist["3"] == 3
        assert expert_dist["4"] == 1
        assert expert_dist["5"] == 1
        assert expert_dist["other"] == 1

        # Mapped 3-tiers for expert
        mapped_tiers = nurse_vs_expert["ktas_expert_mapped_3_tiers"]
        assert mapped_tiers["EMERGENCY"] == 4  # 1 (2) + 2 (2)
        assert mapped_tiers["URGENT"] == 3     # 3 (3)
        assert mapped_tiers["ROUTINE"] == 2    # 4 (1) + 5 (1)
        assert mapped_tiers["unmapped"] == 1   # invalid 9 (1)

        # Nurse distribution is recorded for audit comparison only
        rn_dist = nurse_vs_expert["ktas_rn_levels_1_to_5_audit_only"]
        assert rn_dist["1"] == 1
        assert rn_dist["2"] == 3


# ── Test Suite 3: Gate 3A Governance & Evaluation Refusal ────────────────────

class TestKTASGate3AGovernanceAndScoring:
    """Validates staged scoring refusal and zero data leakage in canonical evaluation records."""

    def test_default_evaluation_refused_without_authorization(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            gate_3a_scoring_authorized=False,
        )
        with pytest.raises(EvaluationRefusedError, match=EXACT_KTAS_REFUSAL_MESSAGE):
            source.load_for_evaluation()

    def test_evaluation_loads_when_authorized(self, synthetic_ktas_data_xlsx: str):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            gate_3a_scoring_authorized=True,
            input_mode=ARM_KTAS_PRIMARY,
        )
        records, counters, manifest = source.load_for_evaluation()

        assert counters.total_records == 10
        # Row 8 has invalid KTAS_expert = 9 and is excluded
        assert counters.valid_records == 9
        assert counters.excluded_records == 1
        assert counters.reasons.get("invalid_or_missing_ktas_expert_label") == 1
        assert len(records) == 9

    def test_input_mode_isolation_and_partial_arm(self, synthetic_ktas_data_xlsx: str):
        source_vital_only = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            gate_3a_scoring_authorized=True,
            input_mode=ARM_KTAS_VITAL_ONLY,
        )
        records_vo, _, _ = source_vital_only.load_for_evaluation()
        for r in records_vo:
            assert r.is_partial_input is True
            assert r.form_data["chief_complaint"] == ""
            assert r.form_data["symptoms"] == []

    def test_prohibited_fields_stripped_and_zero_raw_complaint_retention(
        self, synthetic_ktas_data_xlsx: str
    ):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            gate_3a_scoring_authorized=True,
        )
        records, _, _ = source.load_for_evaluation()

        prohibited_set = set(KTAS_PROHIBITED_FIELDS)
        for rec in records:
            fd = rec.form_data
            # 1. Zero prohibited fields in form_data
            for pf in prohibited_set:
                assert pf not in fd
                assert pf.lower() not in fd

            # 2. Free-text complaints strictly empty string
            assert fd.get("chief_complaint") == ""
            assert rec.raw_fields == {}

            # 3. Reference label is always one of the 3 canonical tiers
            assert rec.reference_label in ("EMERGENCY", "URGENT", "ROUTINE")

    def test_bp_inversion_handled_safely(self, synthetic_ktas_data_xlsx: str):
        source = KTAS2019Source(
            file_path=synthetic_ktas_data_xlsx,
            gate_3a_scoring_authorized=True,
        )
        records, _, _ = source.load_for_evaluation()
        # Row 7 had inverted BP (SBP 80 <= DBP 90)
        rec_7 = [r for r in records if r.source_row_id == 8][0]
        assert rec_7.form_data["bp_systolic"] is None
        assert rec_7.form_data["bp_diastolic"] is None


# ── Test Suite 4: CLI E2E Execution & Output Schema ───────────────────────────

class TestKTASCLIE2EAndZeroLeakage:
    """Validates command-line interface execution, JSON report schema, and strict zero-leakage."""

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
        # A single row with BT, HR, SBP, Saturation, but missing DBP
        row = [2, 1, 45, 1, 2, "흉통", 1, 1, 5, 120, None, 80, 16, 36.5, 98, 2, "CAD", 1, 2, 0, 60, 5, 0]
        rows = [SYNTHETIC_KTAS_HEADERS, row]
        content = create_synthetic_xlsx_bytes("N=1267 data", rows)
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


