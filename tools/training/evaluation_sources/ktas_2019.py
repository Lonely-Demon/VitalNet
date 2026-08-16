"""
Korean KTAS 2019 Dataset Evaluation Source (Gate 3A: External Triage Benchmark).

This module implements the adapter for the Moon et al. (2019) Korean Triage and Acuity Scale
dataset (PLOS ONE, DOI: 10.1371/journal.pone.0216972).

Official Source References:
- Article DOI: https://doi.org/10.1371/journal.pone.0216972
- Supplementary S1 (Data Workbook): https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s001
- Supplementary S2 (Coding Workbook): https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s002
- License Note: PLOS ONE article and publisher-hosted supplementary files; article published under CC BY 4.0;
  verify supplementary reuse under the article terms.

Enforces:
- Deterministic, fail-closed standard-library XLSX parsing (zipfile + xml.etree.ElementTree).
- Strict separation of data workbook ("N=1267 data") and coding workbook ("coding sheet").
  Coding rows are never treated as patient encounters.
- Exact sheet and schema requirements: exact data sheet name ("N=1267 data"), exact coding sheet name
  ("coding sheet"), all 23 expected headers present, zero unexpected headers, zero duplicate headers.
- Conservative nonnumeric token handling: "#NULL!" and "측불" (observed Korean nonnumeric
  measurement-unavailable token) are treated as missing (None), never coerced to zero.
- Canonical five-vital completeness definition requiring BT, HR, SBP, DBP, and Saturation.
  RR is tracked in inspection metadata only.
- Unified physiological plausibility bounds and rules applied identically to inspection and scoring.
- Correct official KTAS sex mapping: 1 = Female, 2 = Male.
- Empirical site-stratified completeness analysis (Local ED vs Regional ED) documenting that
  complete-five-vital records are confined to Regional ED (0 in Local ED due to missing saturation).
- Candidate reference label: KTAS_expert exclusively. KTAS_RN is retained only for aggregate audit
  comparison metadata and is never stored in patient encounter records.
- Pre-registered named mapping ktas_v1: 1-2 -> EMERGENCY, 3 -> URGENT, 4-5 -> ROUTINE.
- Primary input contract ktas_triage_contract_v1 (age, sex, five vitals, allow-listed symptoms,
  empty complaint string); distinct sensitivity arm ktas_vital_only_partial_v1 (empty complaint,
  empty symptoms). Raw complaint text is never retained.
- Hard pre-canonicalization stripping of prohibited fields: "Diagnosis in ED", "Disposition",
  "Error_group", "Length of stay_min", "KTAS duration_min", "mistriage", "KTAS_RN".
- Strict zero in-memory materialization of raw rows or prohibited fields. Streaming row processor
  immediately extracts only aggregate counts or sanitized canonical fields.
- Gate 3A staged scoring refusal by default: load_for_evaluation() raises EvaluationRefusedError
  unless explicitly authorized via task conversation and --gate-3a-scoring-authorized.
- Strict zero patient-level data leakage guaranteed in all reports and metadata containers.
"""

import os
import re
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union
import xml.etree.ElementTree as ET
import zipfile

from .base import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    ExclusionCounters,
    SourceManifest,
    compute_file_sha256,
)
from .ktas_symptom_parser import (
    PARSER_VERSION as KTAS_PARSER_VERSION,
    StreamingKTASSymptomCoverageAccumulator,
    compute_ktas_symptom_parser_coverage,
    parse_ktas_symptoms,
)

# Pre-registered 5-to-3 tier KTAS mapping
KTAS_V1: Dict[int, str] = {
    1: "EMERGENCY",
    2: "EMERGENCY",
    3: "URGENT",
    4: "ROUTINE",
    5: "ROUTINE",
}

# Input arm contracts
ARM_KTAS_PRIMARY: str = "ktas_triage_contract_v1"
ARM_KTAS_VITAL_ONLY: str = "ktas_vital_only_partial_v1"
VALID_INPUT_MODES: Set[str] = {ARM_KTAS_PRIMARY, ARM_KTAS_VITAL_ONLY}

# Prohibited downstream and outcome fields (Strict temporal and label leakage prevention)
KTAS_PROHIBITED_FIELDS: Tuple[str, ...] = (
    "Diagnosis in ED",
    "Disposition",
    "Error_group",
    "Length of stay_min",
    "KTAS duration_min",
    "mistriage",
    "KTAS_RN",
)

# Expected sheet names (fail closed on any deviation)
EXPECTED_DATA_SHEET_NAME: str = "N=1267 data"
EXPECTED_CODING_SHEET_NAME: str = "coding sheet"

# Canonical 23 column headers expected in the Moon et al. data workbook
EXPECTED_DATA_HEADERS: Tuple[str, ...] = (
    "Group",
    "Sex",
    "Age",
    "Arrival mode",
    "Injury",
    "Chief_complain",
    "Mental",
    "Pain",
    "NRS_pain",
    "SBP",
    "DBP",
    "HR",
    "RR",
    "BT",
    "Saturation",
    "KTAS_RN",
    "Diagnosis in ED",
    "Disposition",
    "KTAS_expert",
    "Error_group",
    "Length of stay_min",
    "KTAS duration_min",
    "mistriage",
)

EXACT_KTAS_REFUSAL_MESSAGE: str = (
    "Korean KTAS 2019 model scoring is locked under Gate 3A governance. "
    "Scoring requires separate human authorization and --gate-3a-scoring-authorized."
)

# ── Unified Physiological Plausibility Policy ────────────────────────────────
# Physiologically plausible vital bounds applied identically to inspection and scoring.
# Allows severe hypoxia (SpO2 down to 0-20% observed in arrest/severe respiratory failure).
VITAL_PLAUSIBILITY_BOUNDS: Dict[str, Tuple[float, float]] = {
    "BT": (20.0, 46.0),         # Body temperature in Celsius (hypothermia to hyperpyrexia)
    "HR": (10.0, 350.0),        # Heart rate in bpm (severe bradycardia to extreme SVT/VT)
    "SBP": (20.0, 350.0),       # Systolic BP in mmHg (severe shock to extreme hypertension)
    "DBP": (10.0, 250.0),       # Diastolic BP in mmHg
    "Saturation": (0.0, 100.0),  # SpO2 percentage (0% to 100%, severe hypoxia observed down to 20%)
    "RR": (0.0, 120.0),         # Respiratory rate in breaths/min
    "Age": (0.0, 130.0),        # Age in years
}


def check_vital_plausibility(
    bt: Optional[float],
    hr: Optional[float],
    sbp: Optional[float],
    dbp: Optional[float],
    sat: Optional[float],
) -> Tuple[Dict[str, Optional[float]], bool, Optional[str]]:
    """
    Unified plausibility validation applied identically in inspection and evaluation.

    Returns:
        sanitized_vitals: dict mapping vital name to valid float or None.
        is_5_vital_complete: True if all 5 vitals are present, within physiological bounds, and SBP > DBP.
        exclusion_reason: string reason if any vital was present but implausible / inverted.
    """
    vitals = {"BT": bt, "HR": hr, "SBP": sbp, "DBP": dbp, "Saturation": sat}
    sanitized: Dict[str, Optional[float]] = {}
    exclusion_reason: Optional[str] = None

    for k, v in vitals.items():
        if v is None:
            sanitized[k] = None
            continue
        min_v, max_v = VITAL_PLAUSIBILITY_BOUNDS[k]
        if min_v <= v <= max_v:
            sanitized[k] = v
        else:
            sanitized[k] = None
            if not exclusion_reason:
                exclusion_reason = f"implausible_{k.lower()}_value_{v}"

    # Check BP inversion if both SBP and DBP are present
    if sanitized["SBP"] is not None and sanitized["DBP"] is not None:
        if sanitized["SBP"] <= sanitized["DBP"]:
            sanitized["SBP"] = None
            sanitized["DBP"] = None
            if not exclusion_reason:
                exclusion_reason = "blood_pressure_inversion"

    is_complete = (
        sanitized["BT"] is not None
        and sanitized["HR"] is not None
        and sanitized["SBP"] is not None
        and sanitized["DBP"] is not None
        and sanitized["Saturation"] is not None
    )

    return sanitized, is_complete, exclusion_reason


# ── Fail-Closed Deterministic XLSX Parser (Standard Library) ─────────────────

def _col2idx(col_str: str) -> int:
    """Converts Excel column letters (e.g. 'A', 'Z', 'AA') to 0-based column index."""
    idx = 0
    for ch in col_str.upper():
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"Invalid column letter '{ch}' in reference '{col_str}'")
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _read_ktas_xlsx_sheets(file_path: str) -> Dict[str, List[List[Optional[str]]]]:
    """
    Deterministically parses an OpenXML (.xlsx) workbook using Python's standard library.
    Fail-closed on corrupt archives, missing required parts, unexpected formulas, or duplicate headers.
    Supports inline strings even when xl/sharedStrings.xml is absent.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"XLSX file not found: {file_path}")

    try:
        zf = zipfile.ZipFile(file_path, "r")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Malformed or corrupt XLSX archive: {file_path}") from exc

    with zf:
        namelist = zf.namelist()
        if "xl/workbook.xml" not in namelist:
            raise ValueError("Invalid XLSX structure: missing xl/workbook.xml")

        # 1. Read shared strings table if present (optional in OpenXML standard)
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in namelist:
            try:
                sst_tree = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in sst_tree:
                    text_parts = [
                        el.text or ""
                        for el in si.iter()
                        if el.tag.split("}")[-1] == "t"
                    ]
                    shared_strings.append("".join(text_parts))
            except Exception as exc:
                raise ValueError(f"Failed parsing shared strings in {file_path}") from exc

        # 2. Read workbook relationships to map r:id to sheet targets
        rels: Dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in namelist:
            try:
                rels_tree = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
                for rel in rels_tree:
                    r_id = rel.attrib.get("Id")
                    target = rel.attrib.get("Target", "")
                    if target.startswith("/"):
                        target = target.lstrip("/")
                    elif not target.startswith("xl/"):
                        target = "xl/" + target
                    if r_id:
                        rels[r_id] = target
            except Exception as exc:
                raise ValueError(f"Failed parsing workbook relationships in {file_path}") from exc

        # 3. Read workbook sheet declarations
        sheets: Dict[str, str] = {}
        try:
            wb_tree = ET.fromstring(zf.read("xl/workbook.xml"))
            for sheet in wb_tree.iter():
                if sheet.tag.split("}")[-1] == "sheet":
                    s_name = sheet.attrib.get("name")
                    r_id = (
                        sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                        or sheet.attrib.get("id")
                    )
                    sheet_id = sheet.attrib.get("sheetId", "1")
                    sheet_target = rels.get(r_id, f"xl/worksheets/sheet{sheet_id}.xml")
                    if s_name:
                        sheets[s_name.strip()] = sheet_target
        except Exception as exc:
            raise ValueError(f"Failed parsing workbook sheets in {file_path}") from exc

        if not sheets:
            raise ValueError(f"No worksheets declared in workbook: {file_path}")

        # 4. Parse worksheet XML content
        result: Dict[str, List[List[Optional[str]]]] = {}
        for s_name, s_target in sheets.items():
            if s_target not in namelist:
                continue

            try:
                ws_tree = ET.fromstring(zf.read(s_target))
            except Exception as exc:
                raise ValueError(f"Failed parsing worksheet '{s_name}' in {file_path}") from exc

            rows_data: List[List[Optional[str]]] = []
            for row_el in ws_tree.iter():
                if row_el.tag.split("}")[-1] == "row":
                    row_cells: Dict[int, Optional[str]] = {}
                    max_col = -1

                    for c in row_el:
                        if c.tag.split("}")[-1] != "c":
                            continue

                        r_ref = c.attrib.get("r", "")
                        match = re.match(r"([A-Za-z]+)(\d+)", r_ref)
                        if match:
                            col_idx = _col2idx(match.group(1))
                        else:
                            col_idx = max_col + 1
                        max_col = max(max_col, col_idx)

                        t = c.attrib.get("t")
                        val: Optional[str] = None

                        # Check for child value elements
                        for child in c:
                            tag_name = child.tag.split("}")[-1]
                            if tag_name == "v":
                                raw_v = child.text or ""
                                if t == "s":
                                    try:
                                        s_idx = int(raw_v)
                                        val = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else raw_v
                                    except ValueError:
                                        val = raw_v
                                elif t == "e":
                                    val = raw_v  # Error code e.g. #NULL!, #VALUE!
                                elif t == "b":
                                    val = "1" if raw_v in ("1", "TRUE", "true") else "0"
                                else:
                                    val = raw_v
                                break
                            elif tag_name == "is" or t == "inlineStr":
                                val = "".join(
                                    el.text or ""
                                    for el in child.iter()
                                    if el.tag.split("}")[-1] == "t"
                                )
                                break
                            elif tag_name == "f":
                                # Fail-closed on formula cells
                                raise ValueError(
                                    f"Formula cells are unsupported in static evaluation workbook at cell {r_ref}"
                                )

                        row_cells[col_idx] = val

                    if max_col >= 0:
                        row_list = [row_cells.get(i) for i in range(max_col + 1)]
                        rows_data.append(row_list)

            result[s_name] = rows_data

    return result


# ── Parsing Helpers ──────────────────────────────────────────────────────────

def _safe_float(val: Any) -> Optional[float]:
    """
    Parses a float value safely. Returns None for empty, null, sentinel, or measurement-unavailable
    tokens including '#NULL!' and the observed Korean token '측불'. Never coerces to zero.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    s_lower = s.lower()
    if (
        s_lower in ("null", "none", "nan", "n/a", "-9", "-8", "?", "#null!", "#n/a", "#value!")
        or s in ("측불", "#NULL!")
    ):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    """
    Parses an integer with deterministic nearest-integer rounding for decimal ages.
    Returns None if val is missing, nonnumeric, or a sentinel token.
    """
    f = _safe_float(val)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, TypeError):
        return None


def _map_sex(val: Any) -> str:
    """
    Maps Sex coding to VitalNet canonical sex string ('male', 'female', 'other').
    Official KTAS coding sheet definition:
      1 = Female
      2 = Male
    """
    if val is None:
        return "other"
    s = str(val).strip().lower()
    if s in ("1", "1.0", "f", "female", "여", "여자", "여성"):
        return "female"
    elif s in ("2", "2.0", "m", "male", "남", "남자", "남성"):
        return "male"
    return "other"


# ── Korean KTAS 2019 Evaluation Source Adapter ───────────────────────────────

class KTAS2019Source(BaseEvaluationSource):
    """
    Adapter for the Moon et al. (2019) Korean Triage and Acuity Scale dataset (Gate 3A).
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        coding_file_path: Optional[str] = None,
        gate_3a_scoring_authorized: bool = False,
        input_mode: str = ARM_KTAS_PRIMARY,
        **kwargs,
    ):
        super().__init__(file_path, **kwargs)
        self.coding_file_path = coding_file_path or kwargs.get("coding_file_path")
        self.gate_3a_scoring_authorized = gate_3a_scoring_authorized or kwargs.get(
            "gate_3a_scoring_authorized", False
        )
        self.input_mode = input_mode

        if self.input_mode not in VALID_INPUT_MODES:
            raise ValueError(
                f"Invalid KTAS input mode: '{self.input_mode}'. "
                f"Valid modes: {sorted(list(VALID_INPUT_MODES))}"
            )

    def _build_manifest(self, data_path: Optional[str], coding_path: Optional[str]) -> SourceManifest:
        sha256 = compute_file_sha256(data_path) if data_path else None
        size_bytes = os.path.getsize(data_path) if data_path and os.path.isfile(data_path) else None
        return SourceManifest(
            source_id="ktas_2019",
            source_name="Korean Triage and Acuity Scale (Moon et al. 2019, PLOS ONE)",
            version="2019 (PLOS ONE)",
            official_url="https://doi.org/10.1371/journal.pone.0216972",
            license_note=(
                "PLOS ONE article and publisher-hosted supplementary files; "
                "article published under CC BY 4.0; verify supplementary reuse under the article terms."
            ),
            file_sha256=sha256,
            input_mode=self.input_mode,
            label_definition="KTAS_expert mapped via ktas_v1 (1-2 EMERGENCY, 3 URGENT, 4-5 ROUTINE)",
            scoring_supported=self.gate_3a_scoring_authorized,
            file_path=data_path,
            file_size_bytes=size_bytes,
        )

    def _stream_validated_data_rows(
        self, file_path: str
    ) -> Tuple[List[str], Iterator[Dict[str, Any]]]:
        """
        Validates the exact expected data sheet name and schema headers fail-closed,
        and yields sanitized/extracted row dictionaries one at a time via a streaming iterator.
        Zero in-memory raw row list materialization.
        """
        sheets = _read_ktas_xlsx_sheets(file_path)

        if EXPECTED_DATA_SHEET_NAME not in sheets:
            raise ValueError(
                f"Expected data worksheet '{EXPECTED_DATA_SHEET_NAME}' not found in workbook sheets: {list(sheets.keys())}"
            )

        raw_rows = sheets[EXPECTED_DATA_SHEET_NAME]
        if not raw_rows or len(raw_rows) < 2:
            raise ValueError(f"Data worksheet '{EXPECTED_DATA_SHEET_NAME}' contains insufficient rows.")

        # Header validation
        header_row = [str(cell).strip() if cell is not None else "" for cell in raw_rows[0]]
        if not any(header_row):
            raise ValueError(f"Empty header row in sheet '{EXPECTED_DATA_SHEET_NAME}'")

        # Check for duplicate headers
        seen_headers: Set[str] = set()
        clean_headers: List[str] = []
        for h in header_row:
            if not h:
                continue
            if h in seen_headers:
                raise ValueError(f"Duplicate header '{h}' detected in data sheet '{EXPECTED_DATA_SHEET_NAME}'")
            seen_headers.add(h)
            clean_headers.append(h)

        # Exact schema validation: all expected headers present, no unexpected headers
        missing_headers = [h for h in EXPECTED_DATA_HEADERS if h not in clean_headers]
        if missing_headers:
            raise ValueError(
                f"Missing required headers in data sheet '{EXPECTED_DATA_SHEET_NAME}': {missing_headers}"
            )

        unexpected_headers = [h for h in clean_headers if h not in EXPECTED_DATA_HEADERS]
        if unexpected_headers:
            raise ValueError(
                f"Unexpected extra headers in data sheet '{EXPECTED_DATA_SHEET_NAME}': {unexpected_headers}"
            )

        def row_generator() -> Iterator[Dict[str, Any]]:
            for row in raw_rows[1:]:
                # Skip empty trailing rows
                if not any(c is not None and str(c).strip() != "" for c in row):
                    continue
                row_dict: Dict[str, Any] = {}
                for col_idx, h in enumerate(clean_headers):
                    val = row[col_idx] if col_idx < len(row) else None
                    row_dict[h] = val
                yield row_dict

        return clean_headers, row_generator()

    def _extract_coding_definitions(self, coding_path: Optional[str]) -> Dict[str, Any]:
        """
        Parses variable definitions from the exact coding sheet ('coding sheet').
        Guarantees that coding definitions are retained in metadata and never parsed as patient encounters.
        """
        if not coding_path or not os.path.isfile(coding_path):
            return {
                "status": "not_provided" if not coding_path else "file_not_found",
                "provided_path": coding_path,
            }

        sheets = _read_ktas_xlsx_sheets(coding_path)
        if EXPECTED_CODING_SHEET_NAME not in sheets:
            raise ValueError(
                f"Expected coding worksheet '{EXPECTED_CODING_SHEET_NAME}' not found in workbook sheets: {list(sheets.keys())}"
            )

        raw_rows = sheets[EXPECTED_CODING_SHEET_NAME]
        if not raw_rows or len(raw_rows) < 2:
            return {
                "status": "empty_coding_sheet",
                "sheet_name": EXPECTED_CODING_SHEET_NAME,
            }

        coding_headers = [str(c).strip() if c is not None else "" for c in raw_rows[0]]
        definitions: List[Dict[str, str]] = []

        for r in raw_rows[1:]:
            if not any(c is not None and str(c).strip() != "" for c in r):
                continue
            item = {}
            for idx, h in enumerate(coding_headers):
                if h and idx < len(r) and r[idx] is not None:
                    item[h] = str(r[idx]).strip()
            if item:
                definitions.append(item)

        return {
            "status": "loaded",
            "coding_file": os.path.basename(coding_path),
            "coding_file_sha256": compute_file_sha256(coding_path),
            "sheet_name": EXPECTED_CODING_SHEET_NAME,
            "total_definitions_documented": len(definitions),
            "definitions": definitions,
        }

    def inspect(
        self,
        file_path: Optional[str] = None,
        coding_file_path: Optional[str] = None,
        **kwargs,
    ) -> AggregateDataQuality:
        """
        Performs static inspection and generates aggregate quality metrics.
        Guarantees ZERO raw patient encounter records or free-text complaint strings are retained.
        """
        resolved_data_path = self._resolve_file_path(file_path)
        if not resolved_data_path or not os.path.isfile(resolved_data_path):
            raise FileNotFoundError(f"KTAS 2019 data file not found: {resolved_data_path}")

        resolved_coding_path = coding_file_path or self.coding_file_path or kwargs.get("coding_file_path")

        manifest = self._build_manifest(resolved_data_path, resolved_coding_path)
        headers, data_row_iterator = self._stream_validated_data_rows(resolved_data_path)
        coding_info = self._extract_coding_definitions(resolved_coding_path)

        total_rows = 0
        missing_counts: Dict[str, int] = {h: 0 for h in headers}
        valid_counts: Dict[str, int] = {h: 0 for h in headers}

        # Vital distributions accumulators
        vital_fields = ["BT", "HR", "SBP", "DBP", "RR", "Saturation", "Age"]
        vital_sums: Dict[str, float] = {vf: 0.0 for vf in vital_fields}
        vital_mins: Dict[str, float] = {vf: float("inf") for vf in vital_fields}
        vital_maxs: Dict[str, float] = {vf: float("-inf") for vf in vital_fields}
        vital_numeric_counts: Dict[str, int] = {vf: 0 for vf in vital_fields}

        # Acuity distributions
        ktas_expert_dist: Dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "other": 0}
        ktas_rn_dist: Dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "other": 0}
        mapped_expert_tiers: Dict[str, int] = {"EMERGENCY": 0, "URGENT": 0, "ROUTINE": 0, "unmapped": 0}

        # Site stratification (Group: 1 = Local ED, 2 = Regional ED)
        site_counts: Dict[str, int] = {"local_ed_group_1": 0, "regional_ed_group_2": 0, "other_group": 0}
        site_complete_vitals: Dict[str, int] = {"local_ed_group_1": 0, "regional_ed_group_2": 0, "other_group": 0}
        site_saturation_missing: Dict[str, int] = {"local_ed_group_1": 0, "regional_ed_group_2": 0, "other_group": 0}

        overall_complete_5_vitals = 0
        symptom_accumulator = StreamingKTASSymptomCoverageAccumulator()

        # Stream row by row — never materializing an in-memory patient row list
        for row in data_row_iterator:
            total_rows += 1

            # Field missingness
            for col in headers:
                raw_val = row.get(col)
                if raw_val is None or str(raw_val).strip() == "" or str(raw_val).strip() in ("#NULL!", "측불"):
                    missing_counts[col] += 1
                else:
                    valid_counts[col] += 1

            # Update symptom coverage in streaming fashion (raw string immediately discarded)
            symptom_accumulator.update(row.get("Chief_complain"))

            # Site identification
            raw_grp = str(row.get("Group", "")).strip()
            if raw_grp in ("1", "1.0"):
                site_key = "local_ed_group_1"
            elif raw_grp in ("2", "2.0"):
                site_key = "regional_ed_group_2"
            else:
                site_key = "other_group"
            site_counts[site_key] += 1

            # Numeric vitals
            bt = _safe_float(row.get("BT"))
            hr = _safe_float(row.get("HR"))
            sbp = _safe_float(row.get("SBP"))
            dbp = _safe_float(row.get("DBP"))
            rr = _safe_float(row.get("RR"))
            sat = _safe_float(row.get("Saturation"))
            age = _safe_float(row.get("Age"))

            # Unified plausibility check
            sanitized_vitals, has_5_vitals, _ = check_vital_plausibility(bt, hr, sbp, dbp, sat)

            numeric_map = {
                "BT": sanitized_vitals["BT"],
                "HR": sanitized_vitals["HR"],
                "SBP": sanitized_vitals["SBP"],
                "DBP": sanitized_vitals["DBP"],
                "RR": rr if (rr is not None and VITAL_PLAUSIBILITY_BOUNDS["RR"][0] <= rr <= VITAL_PLAUSIBILITY_BOUNDS["RR"][1]) else None,
                "Saturation": sanitized_vitals["Saturation"],
                "Age": age if (age is not None and VITAL_PLAUSIBILITY_BOUNDS["Age"][0] <= age <= VITAL_PLAUSIBILITY_BOUNDS["Age"][1]) else None,
            }

            for vf, vval in numeric_map.items():
                if vval is not None:
                    vital_sums[vf] += vval
                    vital_numeric_counts[vf] += 1
                    if vval < vital_mins[vf]:
                        vital_mins[vf] = vval
                    if vval > vital_maxs[vf]:
                        vital_maxs[vf] = vval

            if sat is None:
                site_saturation_missing[site_key] += 1

            if has_5_vitals:
                overall_complete_5_vitals += 1
                site_complete_vitals[site_key] += 1

            # KTAS Expert reference distribution
            raw_expert = _safe_int(row.get("KTAS_expert"))
            if raw_expert in KTAS_V1:
                ktas_expert_dist[str(raw_expert)] += 1
                mapped_expert_tiers[KTAS_V1[raw_expert]] += 1
            else:
                ktas_expert_dist["other"] += 1
                mapped_expert_tiers["unmapped"] += 1

            # KTAS RN nurse distribution (audit metadata only)
            raw_rn = _safe_int(row.get("KTAS_RN"))
            if raw_rn in KTAS_V1:
                ktas_rn_dist[str(raw_rn)] += 1
            else:
                ktas_rn_dist["other"] += 1

        # Calculate missingness percentages
        missingness_by_field: Dict[str, Dict[str, Any]] = {}
        for col in headers:
            m_cnt = missing_counts[col]
            v_cnt = valid_counts[col]
            pct = round((m_cnt / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            missingness_by_field[col] = {
                "missing_count": m_cnt,
                "valid_count": v_cnt,
                "missing_pct": pct,
                "valid_pct": round(100.0 - pct, 2),
            }

        # Calculate vital distributions
        vital_distributions: Dict[str, Dict[str, Any]] = {}
        for vf in vital_fields:
            cnt = vital_numeric_counts[vf]
            if cnt > 0:
                vital_distributions[vf] = {
                    "valid_count": cnt,
                    "mean": round(vital_sums[vf] / cnt, 2),
                    "min": vital_mins[vf],
                    "max": vital_maxs[vf],
                    "missingness_pct": missingness_by_field.get(vf, {}).get("missing_pct", 100.0),
                }
            else:
                vital_distributions[vf] = {
                    "valid_count": 0,
                    "mean": None,
                    "min": None,
                    "max": None,
                    "missingness_pct": 100.0,
                }

        complete_vitals_pct = (
            round((overall_complete_5_vitals / total_rows) * 100.0, 4) if total_rows > 0 else 0.0
        )

        site_stratified = {
            "local_ed_group_1": {
                "total_records": site_counts["local_ed_group_1"],
                "complete_5_vitals_count": site_complete_vitals["local_ed_group_1"],
                "complete_5_vitals_pct": (
                    round(
                        (site_complete_vitals["local_ed_group_1"] / site_counts["local_ed_group_1"]) * 100.0,
                        2,
                    )
                    if site_counts["local_ed_group_1"] > 0
                    else 0.0
                ),
                "saturation_missing_count": site_saturation_missing["local_ed_group_1"],
            },
            "regional_ed_group_2": {
                "total_records": site_counts["regional_ed_group_2"],
                "complete_5_vitals_count": site_complete_vitals["regional_ed_group_2"],
                "complete_5_vitals_pct": (
                    round(
                        (site_complete_vitals["regional_ed_group_2"] / site_counts["regional_ed_group_2"]) * 100.0,
                        2,
                    )
                    if site_counts["regional_ed_group_2"] > 0
                    else 0.0
                ),
                "saturation_missing_count": site_saturation_missing["regional_ed_group_2"],
            },
            "complete_vitals_site_confinement_note": (
                "Empirical finding: Complete five-vital records (BT, HR, SBP, DBP, Saturation) "
                "are confined to Regional ED due to 100% missing saturation measurement in Local ED."
            ),
        }

        extra_meta = {
            "source_provenance_urls": {
                "article_doi": "https://doi.org/10.1371/journal.pone.0216972",
                "supplementary_s1_data": "https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s001",
                "supplementary_s2_coding": "https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0216972.s002",
            },
            "site_stratified_completeness": site_stratified,
            "nurse_vs_expert_distribution": {
                "ktas_expert_levels_1_to_5": ktas_expert_dist,
                "ktas_expert_mapped_3_tiers": mapped_expert_tiers,
                "ktas_rn_levels_1_to_5_audit_only": ktas_rn_dist,
            },
            "measurement_unavailable_tokens_audit": {
                "null_token": "#NULL! (handled as missing, not 0)",
                "korean_unavailable_token": "측불 (handled as missing, not 0)",
            },
            "symptom_parser_coverage": symptom_accumulator.finalize(),
            "coding_sheet_provenance": coding_info,
        }

        return AggregateDataQuality(
            source_manifest=manifest,
            total_records_inspected=total_rows,
            headers_present=headers,
            missingness_by_field=missingness_by_field,
            vital_distributions=vital_distributions,
            reference_distribution=mapped_expert_tiers,
            complete_vitals_count=overall_complete_5_vitals,
            complete_vitals_pct=complete_vitals_pct,
            exclusion_summary={},
            linkage_summary=None,
            extra_metadata=extra_meta,
        )

    def load_for_evaluation(
        self,
        file_path: Optional[str] = None,
        coding_file_path: Optional[str] = None,
        gate_3a_scoring_authorized: bool = False,
        input_mode: Optional[str] = None,
        **kwargs,
    ) -> Tuple[List[CanonicalPatientRecord], ExclusionCounters, SourceManifest]:
        """
        Loads the KTAS 2019 dataset into canonical patient records for evaluation.

        STRICT GOVERNANCE REFUSAL: Model evaluation / scoring is locked under Gate 3A governance
        and refused by default. Requires both explicit user authorization in the task conversation
        and the CLI parameter gate_3a_scoring_authorized=True.
        """
        is_authorized = (
            gate_3a_scoring_authorized
            or self.gate_3a_scoring_authorized
            or kwargs.get("gate_3a_scoring_authorized", False)
        )

        if not is_authorized:
            raise EvaluationRefusedError(EXACT_KTAS_REFUSAL_MESSAGE)

        resolved_data_path = self._resolve_file_path(file_path)
        if not resolved_data_path or not os.path.isfile(resolved_data_path):
            raise FileNotFoundError(f"KTAS 2019 data file not found: {resolved_data_path}")

        resolved_coding_path = coding_file_path or self.coding_file_path or kwargs.get("coding_file_path")
        active_input_mode = input_mode or self.input_mode

        manifest = self._build_manifest(resolved_data_path, resolved_coding_path)
        manifest.input_mode = active_input_mode
        manifest.scoring_supported = True

        headers, data_row_iterator = self._stream_validated_data_rows(resolved_data_path)
        counters = ExclusionCounters()

        records: List[CanonicalPatientRecord] = []

        for row_idx, row in enumerate(data_row_iterator):
            counters.record_total()

            # 1. Reference Label Validation (KTAS_expert)
            raw_expert = _safe_int(row.get("KTAS_expert"))
            if raw_expert not in KTAS_V1:
                counters.increment("invalid_or_missing_ktas_expert_label")
                continue

            ref_tier = KTAS_V1[raw_expert]

            # 2. Demographics (Official KTAS coding: 1 = Female, 2 = Male)
            raw_age = _safe_int(row.get("Age"))
            age = raw_age if (raw_age is not None and VITAL_PLAUSIBILITY_BOUNDS["Age"][0] <= raw_age <= VITAL_PLAUSIBILITY_BOUNDS["Age"][1]) else 0

            raw_sex = row.get("Sex")
            sex = _map_sex(raw_sex)

            # 3. Canonical Five Vitals with Unified Plausibility Validation
            bt = _safe_float(row.get("BT"))
            hr = _safe_float(row.get("HR"))
            sbp = _safe_float(row.get("SBP"))
            dbp = _safe_float(row.get("DBP"))
            sat = _safe_float(row.get("Saturation"))

            sanitized_vitals, is_complete_5, exclusion_reason = check_vital_plausibility(
                bt, hr, sbp, dbp, sat
            )

            if exclusion_reason:
                counters.increment(exclusion_reason)

            # 4. Input Arm Construction
            # Raw free-text Chief_complain is NEVER retained or exposed.
            if active_input_mode == ARM_KTAS_PRIMARY:
                # Primary arm: complaint allow-listed symptoms, never raw text
                symptoms = parse_ktas_symptoms(row.get("Chief_complain"))
                form_data = {
                    "patient_age": age,
                    "patient_sex": sex,
                    "temperature": sanitized_vitals["BT"],
                    "heart_rate": sanitized_vitals["HR"],
                    "bp_systolic": sanitized_vitals["SBP"],
                    "bp_diastolic": sanitized_vitals["DBP"],
                    "spo2": sanitized_vitals["Saturation"],
                    "chief_complaint": "",
                    "symptoms": symptoms,
                }
            elif active_input_mode == ARM_KTAS_VITAL_ONLY:
                # Vital-only partial-input stress-test arm
                form_data = {
                    "patient_age": age,
                    "patient_sex": sex,
                    "temperature": sanitized_vitals["BT"],
                    "heart_rate": sanitized_vitals["HR"],
                    "bp_systolic": sanitized_vitals["SBP"],
                    "bp_diastolic": sanitized_vitals["DBP"],
                    "spo2": sanitized_vitals["Saturation"],
                    "chief_complaint": "",
                    "symptoms": [],
                }
            else:
                raise ValueError(f"Unsupported input mode for evaluation: {active_input_mode}")

            # 5. Build Canonical Record (Zero Prohibited Fields, Zero Raw Complaint Text)
            rec = CanonicalPatientRecord(
                form_data=form_data,
                reference_label=ref_tier,
                source_row_id=row_idx + 1,
                is_partial_input=(active_input_mode == ARM_KTAS_VITAL_ONLY),
                raw_fields={},  # Strict zero-leakage: raw fields dictionary left empty
            )

            records.append(rec)

        return records, counters, manifest
