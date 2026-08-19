"""
Generic CSV Evaluation Source (Backward Compatible).

Encapsulates loading and inspection of arbitrary real or synthetic patient CSV datasets
with support for column aliases, 5-level acuity scale mapping (ESI/KTAS), Fahrenheit to
Celsius temperature conversion, and allow-listed symptom extraction.
"""

import csv
import os
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    ExclusionCounters,
    SourceManifest,
    TIER_NAMES,
    compute_file_sha256,
)

# Standard acuity scales mapping 5-level acuity to VitalNet's 3 tiers
ACUITY_MAPS: Dict[str, Dict[int, int]] = {
    "esi": {1: 2, 2: 2, 3: 1, 4: 0, 5: 0},
    "ktas": {1: 2, 2: 2, 3: 1, 4: 0, 5: 0},
}

ALLOWED_SYMPTOMS = {
    "chest_pain",
    "breathlessness",
    "altered_consciousness",
    "severe_bleeding",
    "seizure",
    "high_fever",
    "severe_abdominal_pain",
    "persistent_vomiting",
    "severe_headache",
    "weakness_one_side",
    "difficulty_speaking",
    "swelling_face_throat",
}


def _get_val(row: Dict[str, Any], *names: str, default: Any = None) -> Any:
    for nm in names:
        if nm in row and str(row[nm]).strip() != "":
            return row[nm]
    return default


def _num(v: Any, cast=float) -> Optional[Any]:
    if v is None or str(v).strip() == "":
        return None
    try:
        return cast(float(v))
    except (ValueError, TypeError):
        return None


def _sex(v: Any) -> str:
    s = str(v or "").strip().lower()
    if s in ("m", "male", "1"):
        return "male"
    if s in ("f", "female", "0"):
        return "female"
    return "other"


def row_to_formdata(row: Dict[str, Any], temp_fahrenheit: bool = False) -> Dict[str, Any]:
    temp = _num(_get_val(row, "temperature", "temp"))
    if temp is not None and temp_fahrenheit:
        temp = round((temp - 32.0) * 5.0 / 9.0, 1)

    raw_symptoms = _get_val(row, "symptoms", default="") or ""
    symptoms = [s.strip() for s in str(raw_symptoms).replace("|", ",").split(",") if s.strip()]
    symptoms = [s for s in symptoms if s in ALLOWED_SYMPTOMS]

    return {
        "patient_age": _num(_get_val(row, "patient_age", "age"), int) or 0,
        "patient_sex": _sex(_get_val(row, "patient_sex", "sex", "gender")),
        "bp_systolic": _num(_get_val(row, "bp_systolic", "sbp"), int),
        "bp_diastolic": _num(_get_val(row, "bp_diastolic", "dbp"), int),
        "spo2": _num(_get_val(row, "spo2", "o2sat"), int),
        "heart_rate": _num(_get_val(row, "heart_rate", "heartrate"), int),
        "temperature": temp,
        "symptoms": symptoms,
        "chief_complaint": str(_get_val(row, "chief_complaint", "chiefcomplaint", default="") or ""),
        "complaint_duration": str(_get_val(row, "complaint_duration", default="") or ""),
        "location": str(_get_val(row, "location", default="") or ""),
        "known_conditions": str(_get_val(row, "known_conditions", default="") or ""),
        "current_medications": str(_get_val(row, "current_medications", default="") or ""),
        "is_pregnant": None,
        "observations": str(_get_val(row, "observations", default="") or ""),
    }


def parse_reference_tier(row: Dict[str, Any], acuity_scale: Optional[str] = "esi") -> Optional[str]:
    rt = _get_val(row, "reference_tier", "tier")
    if rt is not None:
        rt_str = str(rt).strip().upper()
        if rt_str in ("ROUTINE", "URGENT", "EMERGENCY"):
            return rt_str
        if rt_str in ("0", "1", "2"):
            return TIER_NAMES.get(int(rt_str))

    acuity = _num(_get_val(row, "reference_acuity", "acuity"), int)
    if acuity is not None and acuity_scale and acuity_scale.lower() in ACUITY_MAPS:
        tier_idx = ACUITY_MAPS[acuity_scale.lower()].get(int(acuity))
        if tier_idx is not None:
            return TIER_NAMES.get(tier_idx)

    return None


class GenericCSVSource(BaseEvaluationSource):
    """
    Adapter for generic labelled CSV patient files.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        acuity_scale: str = "esi",
        temp_fahrenheit: bool = False,
        **kwargs,
    ):
        super().__init__(file_path, **kwargs)
        self.acuity_scale = acuity_scale
        self.temp_fahrenheit = temp_fahrenheit

    def _build_manifest(self, path: Optional[str]) -> SourceManifest:
        sha256 = compute_file_sha256(path) if path else None
        size_bytes = os.path.getsize(path) if path and os.path.isfile(path) else None
        base_name = os.path.basename(path) if path else "generic.csv"
        return SourceManifest(
            source_id="generic_csv",
            source_name=f"Generic CSV Evaluation Source ({base_name})",
            version="1.0",
            official_url="User-provided CSV dataset",
            license_note="User-specified Data Access Terms",
            file_sha256=sha256,
            input_mode="full_input",
            label_definition=f"acuity_scale={self.acuity_scale} / reference_tier",
            scoring_supported=True,
            file_path=path,
            file_size_bytes=size_bytes,
        )

    def inspect(self, file_path: Optional[str] = None, **kwargs) -> AggregateDataQuality:
        """
        Inspect generic CSV file and output aggregate data quality metrics.
        """
        resolved_path = self._resolve_file_path(file_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"CSV source file not found: {resolved_path}")

        manifest = self._build_manifest(resolved_path)
        total_rows = 0
        valid_rows = 0
        unusable_ref_count = 0
        headers_detected: List[str] = []

        tier_counts: Dict[str, int] = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0, "unusable": 0}
        vital_fields = ["temperature", "heart_rate", "bp_systolic", "bp_diastolic", "spo2"]
        present_counts: Dict[str, int] = {vf: 0 for vf in vital_fields}
        vital_sums: Dict[str, float] = {vf: 0.0 for vf in vital_fields}
        vital_mins: Dict[str, float] = {vf: float("inf") for vf in vital_fields}
        vital_maxs: Dict[str, float] = {vf: float("-inf") for vf in vital_fields}
        complete_vitals_count = 0

        with open(resolved_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                headers_detected = list(reader.fieldnames)

            for row in reader:
                total_rows += 1
                ref_label = parse_reference_tier(row, self.acuity_scale)
                if ref_label is None:
                    unusable_ref_count += 1
                    tier_counts["unusable"] += 1
                else:
                    tier_counts[ref_label] = tier_counts.get(ref_label, 0) + 1
                    valid_rows += 1

                fd = row_to_formdata(row, self.temp_fahrenheit)
                is_comp = True
                for vf in vital_fields:
                    val = fd.get(vf)
                    if val is not None:
                        present_counts[vf] += 1
                        vital_sums[vf] += float(val)
                        if float(val) < vital_mins[vf]:
                            vital_mins[vf] = float(val)
                        if float(val) > vital_maxs[vf]:
                            vital_maxs[vf] = float(val)
                    else:
                        is_comp = False

                if is_comp:
                    complete_vitals_count += 1

        missingness_by_field: Dict[str, Dict[str, Any]] = {}
        for vf in vital_fields:
            pres = present_counts[vf]
            miss = total_rows - pres
            pct = round((miss / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            missingness_by_field[vf] = {
                "missing_count": miss,
                "valid_count": pres,
                "missing_pct": pct,
                "valid_pct": round(100.0 - pct, 2),
            }

        vital_distributions: Dict[str, Dict[str, Any]] = {}
        for vf in vital_fields:
            cnt = present_counts[vf]
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

        complete_pct = (
            round((complete_vitals_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
        )

        return AggregateDataQuality(
            source_manifest=manifest,
            total_records_inspected=total_rows,
            headers_present=headers_detected,
            missingness_by_field=missingness_by_field,
            vital_distributions=vital_distributions,
            reference_distribution=tier_counts,
            complete_vitals_count=complete_vitals_count,
            complete_vitals_pct=complete_pct,
            exclusion_summary={"unusable_reference": unusable_ref_count},
            linkage_summary=None,
            extra_metadata={
                "acuity_scale": self.acuity_scale,
                "temp_fahrenheit": self.temp_fahrenheit,
            },
        )

    def load_for_evaluation(
        self, file_path: Optional[str] = None, **kwargs
    ) -> Tuple[List[CanonicalPatientRecord], ExclusionCounters, SourceManifest]:
        """
        Loads CSV records into CanonicalPatientRecord objects for evaluation.
        """
        resolved_path = self._resolve_file_path(file_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"CSV source file not found: {resolved_path}")

        manifest = self._build_manifest(resolved_path)
        counters = ExclusionCounters()
        records: List[CanonicalPatientRecord] = []

        with open(resolved_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=1):
                counters.record_total()
                ref_label = parse_reference_tier(row, self.acuity_scale)
                if ref_label is None:
                    counters.increment("unusable_reference")
                    continue

                fd = row_to_formdata(row, self.temp_fahrenheit)
                record = CanonicalPatientRecord(
                    form_data=fd,
                    reference_label=ref_label,
                    source_row_id=idx,
                    is_partial_input=False,
                    survey_weight=None,
                    raw_fields=row,
                )
                counters.record_valid()
                records.append(record)

        return records, counters, manifest
