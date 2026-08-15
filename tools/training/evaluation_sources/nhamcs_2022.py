"""
CDC NHAMCS 2022 Emergency Department File Evaluation Source (Gate 1B).

This module implements the fixed-width ASCII parser and partial-input adapter for the
CDC National Hospital Ambulatory Medical Care Survey 2022 Emergency Department file (ed2022).

Enforces:
- Exact CDC fixed-width column offsets.
- Fahrenheit tenths to Celsius conversion for body temperature.
- Doppler code 998 and physiological range filtering.
- Sentinel IMMEDR exclusions (-9, -8, 0, 7) tracked in granular exclusion counters.
- nhamcs_immediacy_v1 proxy ground truth mapping (1/2 -> EMERGENCY, 3 -> URGENT, 4/5 -> ROUTINE).
- Strict partial_input mode: empty chief complaint and symptoms, no synthetic text generation.
- Survey expansion weights (PATWT) preserved in metadata only; strictly excluded from model metric weighting.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    ExclusionCounters,
    SourceManifest,
    compute_file_sha256,
)

# CDC NHAMCS 2022 Immediacy mapping (nhamcs_immediacy_v1)
NHAMCS_IMMEDIACY_V1: Dict[int, str] = {
    1: "EMERGENCY",  # Immediate (<1 min)
    2: "EMERGENCY",  # Emergent (1-14 min)
    3: "URGENT",     # Urgent (15-60 min)
    4: "ROUTINE",    # Semi-urgent (61-120 min)
    5: "ROUTINE",    # Nonurgent (121 min-24 hr)
}


class NHAMCS2022Source(BaseEvaluationSource):
    """
    Fixed-width parser and evaluation loader for CDC NHAMCS 2022 Emergency Department file.
    """

    def __init__(self, file_path: Optional[str] = None, **kwargs):
        super().__init__(file_path, **kwargs)

    def _build_manifest(self, path: Optional[str]) -> SourceManifest:
        sha256 = compute_file_sha256(path) if path else None
        size_bytes = os.path.getsize(path) if path and os.path.isfile(path) else None
        return SourceManifest(
            source_id="nhamcs_2022",
            source_name="CDC NHAMCS 2022 Emergency Department Summary (ed2022)",
            version="2022 Public Use File",
            official_url="https://www.cdc.gov/nchs/ahcd/datasets_documentation_related.htm",
            license_note="CDC Public Use Data Agreement (100% de-identified)",
            file_sha256=sha256,
            input_mode="partial_input",
            label_definition="nhamcs_immediacy_v1 (1/2 -> EMERGENCY, 3 -> URGENT, 4/5 -> ROUTINE)",
            scoring_supported=True,
            file_path=path,
            file_size_bytes=size_bytes,
        )

    def _parse_line(
        self, line: str, line_idx: int, counters: Optional[ExclusionCounters] = None
    ) -> Tuple[Optional[CanonicalPatientRecord], Optional[Dict[str, Any]], Optional[str]]:
        """
        Parses a single fixed-width line from ed2022.

        Returns:
            Tuple of (CanonicalPatientRecord or None, InspectionDict or None, ExclusionReason or None)
        """
        line_clean = line.rstrip("\r\n")
        if len(line_clean) < 68:
            if counters:
                counters.increment("short_line_format")
            return None, None, "short_line_format"

        # 1. Survey Year Check (Cols 1-4, [0:4])
        raw_year = line_clean[0:4].strip()

        # 2. Age Parsing (Cols 16-18, [15:18])
        raw_age = line_clean[15:18].strip()
        if not raw_age or raw_age in ("-9", "-8"):
            if counters:
                counters.increment("invalid_age")
            return None, None, "invalid_age"
        try:
            age_int = int(raw_age)
            if 0 <= age_int <= 94:
                patient_age = age_int
            else:
                if counters:
                    counters.increment("invalid_age")
                return None, None, "invalid_age"
        except ValueError:
            if counters:
                counters.increment("invalid_age")
            return None, None, "invalid_age"

        # 3. Sex Mapping (Col 25, [24:25])
        raw_sex = line_clean[24:25].strip()
        if raw_sex == "1":
            patient_sex = "female"
        elif raw_sex == "2":
            patient_sex = "male"
        else:
            if counters:
                counters.increment("invalid_sex")
            return None, None, "invalid_sex"

        # 4. Temperature (Cols 48-51, [47:51]) in tenths of Fahrenheit
        raw_temp = line_clean[47:51].strip()
        temperature: Optional[float] = None
        if raw_temp and raw_temp not in ("-9", "-8", "9999"):
            try:
                temp_val = int(raw_temp)
                if 896 <= temp_val <= 1056:
                    temp_f = temp_val / 10.0
                    temperature = round((temp_f - 32.0) * 5.0 / 9.0, 1)
            except ValueError:
                temperature = None

        # 5. Pulse (Cols 52-54, [51:54])
        raw_pulse = line_clean[51:54].strip()
        heart_rate: Optional[int] = None
        is_doppler_pulse = False
        if raw_pulse == "998":
            is_doppler_pulse = True
        elif raw_pulse and raw_pulse not in ("-9", "-8"):
            try:
                pulse_val = int(raw_pulse)
                if 0 <= pulse_val <= 240:
                    heart_rate = pulse_val
            except ValueError:
                heart_rate = None

        # 6. Respiratory Rate (Cols 55-57, [54:57]) — Inspection metadata only!
        raw_respr = line_clean[54:57].strip()
        respiratory_rate: Optional[int] = None
        if raw_respr and raw_respr not in ("-9", "-8"):
            try:
                respr_val = int(raw_respr)
                # Official NHAMCS codebook range: 0-150 breaths/min (metadata only, not passed to model)
                if 0 <= respr_val <= 150:
                    respiratory_rate = respr_val
            except ValueError:
                respiratory_rate = None

        # 7. Blood Pressure Systolic (Cols 58-60, [57:60])
        raw_sbp = line_clean[57:60].strip()
        bp_systolic: Optional[int] = None
        if raw_sbp and raw_sbp not in ("-9", "-8", "0", "000"):
            try:
                sbp_val = int(raw_sbp)
                if 43 <= sbp_val <= 289:
                    bp_systolic = sbp_val
            except ValueError:
                bp_systolic = None

        # 8. Blood Pressure Diastolic (Cols 61-63, [60:63])
        raw_dbp = line_clean[60:63].strip()
        bp_diastolic: Optional[int] = None
        is_doppler_dbp = False
        if raw_dbp == "998":
            is_doppler_dbp = True
        elif raw_dbp and raw_dbp not in ("-9", "-8", "0", "000"):
            try:
                dbp_val = int(raw_dbp)
                if 22 <= dbp_val <= 190:
                    bp_diastolic = dbp_val
            except ValueError:
                bp_diastolic = None

        # Physiological BP consistency check
        if bp_systolic is not None and bp_diastolic is not None:
            if bp_diastolic >= bp_systolic:
                bp_systolic = None
                bp_diastolic = None

        # 9. Pulse Oximetry SpO2 (Cols 64-66, [63:66])
        raw_spo2 = line_clean[63:66].strip()
        spo2: Optional[int] = None
        if raw_spo2 and raw_spo2 not in ("-9", "-8"):
            try:
                o2_val = int(raw_spo2)
                if 0 <= o2_val <= 100:
                    spo2 = o2_val
            except ValueError:
                spo2 = None

        # 10. IMMEDR Immediacy (Cols 67-68, [66:68])
        raw_immedr = line_clean[66:68].strip()
        immedr_code: Optional[int] = None
        reference_label: Optional[str] = None

        if raw_immedr == "-9":
            if counters:
                counters.increment("sentinel_immedr_minus_9")
            return None, None, "sentinel_immedr_minus_9"
        elif raw_immedr == "-8":
            if counters:
                counters.increment("sentinel_immedr_minus_8")
            return None, None, "sentinel_immedr_minus_8"
        elif raw_immedr in ("0", "00"):
            if counters:
                counters.increment("sentinel_immedr_0")
            return None, None, "sentinel_immedr_0"
        elif raw_immedr in ("7", "07"):
            if counters:
                counters.increment("sentinel_immedr_7")
            return None, None, "sentinel_immedr_7"
        else:
            try:
                code_val = int(raw_immedr)
                if code_val in NHAMCS_IMMEDIACY_V1:
                    immedr_code = code_val
                    reference_label = NHAMCS_IMMEDIACY_V1[code_val]
                else:
                    if counters:
                        counters.increment("sentinel_immedr_out_of_range")
                    return None, None, "sentinel_immedr_out_of_range"
            except ValueError:
                if counters:
                    counters.increment("sentinel_immedr_invalid")
                return None, None, "sentinel_immedr_invalid"

        # 11. Survey Design Variables (PATWT cols 179-188 [178:188])
        patwt: Optional[float] = None
        if len(line_clean) >= 188:
            raw_patwt = line_clean[178:188].strip()
            if raw_patwt:
                try:
                    patwt = float(raw_patwt)
                except ValueError:
                    patwt = None

        # Build Canonical Patient Record in strict partial_input mode
        form_data = {
            "patient_age": patient_age,
            "patient_sex": patient_sex,
            "bp_systolic": bp_systolic,
            "bp_diastolic": bp_diastolic,
            "spo2": spo2,
            "heart_rate": heart_rate,
            "temperature": temperature,
            "symptoms": [],                 # STRICT: Partial-input mode
            "chief_complaint": "",          # STRICT: Partial-input mode
            "chief_complaint_available": False,  # Explicit partial-input flag
            "complaint_duration": "",
            "location": "",
            "known_conditions": "",
            "current_medications": "",
            "is_pregnant": None,
            "observations": "",
        }

        record = CanonicalPatientRecord(
            form_data=form_data,
            reference_label=reference_label,
            source_row_id=line_idx,
            is_partial_input=True,
            survey_weight=patwt,
            raw_fields={
                "raw_age": raw_age,
                "raw_sex": raw_sex,
                "raw_immedr": raw_immedr,
                "respiratory_rate": respiratory_rate,
                "is_doppler_pulse": is_doppler_pulse,
                "is_doppler_dbp": is_doppler_dbp,
                "survey_year": raw_year,
            },
        )

        insp_dict = {
            "patient_age": patient_age,
            "patient_sex": patient_sex,
            "bp_systolic": bp_systolic,
            "bp_diastolic": bp_diastolic,
            "spo2": spo2,
            "heart_rate": heart_rate,
            "temperature": temperature,
            "respiratory_rate": respiratory_rate,
            "immedr_code": immedr_code,
            "reference_label": reference_label,
            "patwt": patwt,
            "is_doppler_pulse": is_doppler_pulse,
            "is_doppler_dbp": is_doppler_dbp,
            "chief_complaint_available": False,
        }

        return record, insp_dict, None

    def inspect(self, file_path: Optional[str] = None, **kwargs) -> AggregateDataQuality:
        """
        Inspect fixed-width ed2022 file and compute aggregate data quality distributions.
        """
        resolved_path = self._resolve_file_path(file_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"CDC NHAMCS 2022 source file not found: {resolved_path}")

        manifest = self._build_manifest(resolved_path)
        counters = ExclusionCounters()

        total_lines = 0
        valid_records_count = 0
        immedr_counts: Dict[str, int] = {str(k): 0 for k in range(1, 6)}
        tier_counts: Dict[str, int] = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
        sentinel_counts: Dict[str, int] = {
            "-9": 0, "-8": 0, "0": 0, "7": 0, "other": 0
        }

        vital_fields = ["temperature", "heart_rate", "bp_systolic", "bp_diastolic", "spo2", "respiratory_rate"]
        present_counts: Dict[str, int] = {vf: 0 for vf in vital_fields}
        vital_sums: Dict[str, float] = {vf: 0.0 for vf in vital_fields}
        vital_mins: Dict[str, float] = {vf: float("inf") for vf in vital_fields}
        vital_maxs: Dict[str, float] = {vf: float("-inf") for vf in vital_fields}

        complete_vitals_count = 0
        patwt_sum = 0.0
        patwt_count = 0
        doppler_pulse_count = 0
        doppler_dbp_count = 0

        with open(resolved_path, mode="r", encoding="latin-1", errors="replace") as f:
            for line_idx, line in enumerate(f, start=1):
                total_lines += 1
                counters.record_total()

                # Basic slicing for sentinel tracking even if excluded
                line_clean = line.rstrip("\r\n")
                if len(line_clean) >= 68:
                    raw_im = line_clean[66:68].strip()
                    if raw_im in sentinel_counts:
                        sentinel_counts[raw_im] += 1
                    elif raw_im in ("00", "0"):
                        sentinel_counts["0"] += 1
                    elif raw_im in ("07", "7"):
                        sentinel_counts["7"] += 1
                    elif raw_im in ("1", "2", "3", "4", "5", "01", "02", "03", "04", "05"):
                        pass
                    else:
                        sentinel_counts["other"] += 1

                record, insp, reason = self._parse_line(line, line_idx, counters)
                if record is not None and insp is not None:
                    valid_records_count += 1
                    counters.record_valid()

                    imm_code = str(insp.get("immedr_code"))
                    if imm_code in immedr_counts:
                        immedr_counts[imm_code] += 1

                    ref_tier = insp.get("reference_label")
                    if ref_tier in tier_counts:
                        tier_counts[ref_tier] += 1

                    # Vitals tracking
                    is_complete = True
                    for vf in ["temperature", "heart_rate", "bp_systolic", "bp_diastolic", "spo2"]:
                        v_val = insp.get(vf)
                        if v_val is not None:
                            present_counts[vf] += 1
                            vital_sums[vf] += v_val
                            if v_val < vital_mins[vf]:
                                vital_mins[vf] = v_val
                            if v_val > vital_maxs[vf]:
                                vital_maxs[vf] = v_val
                        else:
                            is_complete = False

                    # RESPR tracking
                    rr_val = insp.get("respiratory_rate")
                    if rr_val is not None:
                        present_counts["respiratory_rate"] += 1
                        vital_sums["respiratory_rate"] += rr_val
                        if rr_val < vital_mins["respiratory_rate"]:
                            vital_mins["respiratory_rate"] = rr_val
                        if rr_val > vital_maxs["respiratory_rate"]:
                            vital_maxs["respiratory_rate"] = rr_val

                    if is_complete:
                        complete_vitals_count += 1

                    if insp.get("is_doppler_pulse"):
                        doppler_pulse_count += 1
                    if insp.get("is_doppler_dbp"):
                        doppler_dbp_count += 1

                    pw = insp.get("patwt")
                    if pw is not None:
                        patwt_sum += pw
                        patwt_count += 1

        # Missingness by field
        missingness_by_field: Dict[str, Dict[str, Any]] = {}
        for vf in vital_fields:
            pres = present_counts[vf]
            miss = valid_records_count - pres
            pct = round((miss / valid_records_count) * 100.0, 2) if valid_records_count > 0 else 0.0
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

        complete_vitals_pct = (
            round((complete_vitals_count / valid_records_count) * 100.0, 2)
            if valid_records_count > 0
            else 0.0
        )

        headers_detected = [
            "VYEAR", "VMONTH", "VDAYR", "ARRTIME", "AGE", "SEX", "TEMPF",
            "PULSE", "RESPR", "BPSYS", "BPDIAS", "POPCT", "IMMEDR", "PATWT",
        ]

        extra_meta = {
            "immedr_distribution": immedr_counts,
            "sentinel_counts_inspected": sentinel_counts,
            "chief_complaint_available": False,
            "doppler_counters": {
                "doppler_pulse_count": doppler_pulse_count,
                "doppler_dbp_count": doppler_dbp_count,
            },
            "survey_design_metadata": {
                "patwt_sampled_encounters": patwt_count,
                "patwt_mean": round(patwt_sum / patwt_count, 2) if patwt_count > 0 else None,
                "patwt_sum_population_estimate": round(patwt_sum, 2),
                "survey_weight_policy": "Strictly excluded from model performance weighting.",
            },
        }

        return AggregateDataQuality(
            source_manifest=manifest,
            total_records_inspected=total_lines,
            headers_present=headers_detected,
            missingness_by_field=missingness_by_field,
            vital_distributions=vital_distributions,
            reference_distribution=tier_counts,
            complete_vitals_count=complete_vitals_count,
            complete_vitals_pct=complete_vitals_pct,
            exclusion_summary=counters.reasons,
            linkage_summary=None,
            extra_metadata=extra_meta,
        )

    def load_for_evaluation(
        self, file_path: Optional[str] = None, **kwargs
    ) -> Tuple[List[CanonicalPatientRecord], ExclusionCounters, SourceManifest]:
        """
        Loads CDC NHAMCS 2022 fixed-width file into canonical patient records for evaluation.
        Enforces strict partial_input mode and returns granular exclusion counters.
        """
        resolved_path = self._resolve_file_path(file_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"CDC NHAMCS 2022 source file not found: {resolved_path}")

        manifest = self._build_manifest(resolved_path)
        counters = ExclusionCounters()
        records: List[CanonicalPatientRecord] = []

        with open(resolved_path, mode="r", encoding="latin-1", errors="replace") as f:
            for line_idx, line in enumerate(f, start=1):
                counters.record_total()
                record, _, reason = self._parse_line(line, line_idx, counters)
                if record is not None:
                    counters.record_valid()
                    records.append(record)

        return records, counters, manifest
