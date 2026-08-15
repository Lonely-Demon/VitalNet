"""
Iran ED Dataset Evaluation Source (Gate 1A: Inspection-Only and Sparse-Input Analysis).

This module implements the adapter for the Kashani et al. Iranian Emergency Department
triage dataset (CC BY 4.0). Under VitalNet's validation protocol, this source is
strictly inspection-only due to its binary urgency ground truth and severe vital sparsity
(only 91 complete 5-vital records out of 143,582 rows).

Model evaluation / scoring is strictly refused.
"""

import csv
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    ExclusionCounters,
    SourceManifest,
    compute_file_sha256,
)

PUBLISHED_HEADERS: List[str] = [
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
]

EXACT_REFUSAL_MESSAGE: str = (
    "Iran ED triage grade is binary in the published source and is unsupported "
    "for three-tier full-input evaluation; inspection/sparse-input analysis only."
)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in ("-9", "-8", "null", "none", "nan"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


class IranEDSource(BaseEvaluationSource):
    """
    Adapter for Iran Emergency Department Triage dataset (Gate 1A).
    Provides aggregate-only data quality inspection; refuses model evaluation.
    """

    def __init__(self, file_path: Optional[str] = None, **kwargs):
        super().__init__(file_path, **kwargs)
        self.linkage_file_path: Optional[str] = kwargs.get("linkage_file_path")

    def _build_manifest(self, path: Optional[str]) -> SourceManifest:
        sha256 = compute_file_sha256(path) if path else None
        size_bytes = os.path.getsize(path) if path and os.path.isfile(path) else None
        return SourceManifest(
            source_id="iran_ed",
            source_name="Iranian Emergency Department Triage Dataset (Kashani et al.)",
            version="2024 (Retrospective Single-Center ED)",
            official_url="https://doi.org/10.1016/j.dib.2024.110298",
            license_note="Creative Commons Attribution 4.0 International (CC BY 4.0)",
            file_sha256=sha256,
            input_mode="not_scored",
            label_definition="published_binary (Grades 1-2 urgent vs 3-5 non-urgent)",
            scoring_supported=False,
            file_path=path,
            file_size_bytes=size_bytes,
        )

    def inspect(
        self,
        file_path: Optional[str] = None,
        linkage_file_path: Optional[str] = None,
        **kwargs,
    ) -> AggregateDataQuality:
        """
        Performs comprehensive aggregate data quality inspection of the Iran ED dataset.
        Zero patient-level records, identifiers, or free-text strings are emitted.
        """
        resolved_path = self._resolve_file_path(file_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"Iran ED source file not found: {resolved_path}")

        resolved_linkage = linkage_file_path or self.linkage_file_path or kwargs.get("linkage_file_path")

        manifest = self._build_manifest(resolved_path)

        total_rows = 0
        headers_detected: List[str] = []
        missing_counts: Dict[str, int] = {h: 0 for h in PUBLISHED_HEADERS}
        valid_counts: Dict[str, int] = {h: 0 for h in PUBLISHED_HEADERS}

        triage_grades: Dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "other": 0}
        binary_urgency: Dict[str, int] = {"urgent_grades_1_2": 0, "non_urgent_grades_3_5": 0, "unclassified": 0}
        critical_status_counts: Dict[str, int] = {"0": 0, "1": 0, "missing": 0, "other": 0}
        fast_execute_counts: Dict[str, int] = {"0": 0, "1": 0, "missing": 0, "other": 0}

        vital_sums: Dict[str, float] = {}
        vital_mins: Dict[str, float] = {}
        vital_maxs: Dict[str, float] = {}
        vital_numeric_counts: Dict[str, int] = {}
        vital_fields = ["BlooddpressurSystol", "BlooddpressurDiastol", "PulseRate", "Temperature", "O2Saturation"]
        for vf in vital_fields:
            vital_sums[vf] = 0.0
            vital_mins[vf] = float("inf")
            vital_maxs[vf] = float("-inf")
            vital_numeric_counts[vf] = 0

        complete_vitals_count = 0
        triage_codes_seen: Set[str] = set()

        with open(resolved_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                headers_detected = list(reader.fieldnames)
                for h in headers_detected:
                    if h not in missing_counts:
                        missing_counts[h] = 0
                        valid_counts[h] = 0

            for row in reader:
                total_rows += 1

                # Check missingness for all columns
                for col in missing_counts.keys():
                    raw_val = row.get(col)
                    if raw_val is None or str(raw_val).strip() == "":
                        missing_counts[col] += 1
                    else:
                        valid_counts[col] += 1

                # Vital signs extraction
                sbp = _safe_float(row.get("BlooddpressurSystol"))
                dbp = _safe_float(row.get("BlooddpressurDiastol"))
                hr = _safe_float(row.get("PulseRate"))
                temp = _safe_float(row.get("Temperature"))
                spo2 = _safe_float(row.get("O2Saturation"))

                vitals = {
                    "BlooddpressurSystol": sbp,
                    "BlooddpressurDiastol": dbp,
                    "PulseRate": hr,
                    "Temperature": temp,
                    "O2Saturation": spo2,
                }

                for vf, vval in vitals.items():
                    if vval is not None:
                        vital_sums[vf] += vval
                        vital_numeric_counts[vf] += 1
                        if vval < vital_mins[vf]:
                            vital_mins[vf] = vval
                        if vval > vital_maxs[vf]:
                            vital_maxs[vf] = vval

                # 5-vital completeness check
                if sbp is not None and dbp is not None and hr is not None and temp is not None and spo2 is not None:
                    complete_vitals_count += 1

                # Triage grade distribution
                raw_grade = str(row.get("TriageGrade", "")).strip()
                if raw_grade in triage_grades:
                    triage_grades[raw_grade] += 1
                    if raw_grade in ("1", "2"):
                        binary_urgency["urgent_grades_1_2"] += 1
                    elif raw_grade in ("3", "4", "5"):
                        binary_urgency["non_urgent_grades_3_5"] += 1
                else:
                    triage_grades["other"] += 1
                    binary_urgency["unclassified"] += 1

                # Critical status
                raw_crit = str(row.get("CriticalStatus", "")).strip()
                if raw_crit in ("0", "1"):
                    critical_status_counts[raw_crit] += 1
                elif not raw_crit:
                    critical_status_counts["missing"] += 1
                else:
                    critical_status_counts["other"] += 1

                # Fast execute
                raw_fast = str(row.get("NeedFastExecute", "")).strip()
                if raw_fast in ("0", "1"):
                    fast_execute_counts[raw_fast] += 1
                elif not raw_fast:
                    fast_execute_counts["missing"] += 1
                else:
                    fast_execute_counts["other"] += 1

                # Triage code collection for linkage
                code = str(row.get("triage_code", "")).strip()
                if code:
                    triage_codes_seen.add(code)

        # Missingness percentages
        missingness_by_field: Dict[str, Dict[str, Any]] = {}
        for col in missing_counts:
            m_cnt = missing_counts[col]
            v_cnt = valid_counts[col]
            pct = round((m_cnt / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            missingness_by_field[col] = {
                "missing_count": m_cnt,
                "valid_count": v_cnt,
                "missing_pct": pct,
                "valid_pct": round(100.0 - pct, 2),
            }

        # Vital distributions
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
            round((complete_vitals_count / total_rows) * 100.0, 4) if total_rows > 0 else 0.0
        )

        # Optional Admission Linkage
        linkage_summary: Optional[Dict[str, Any]] = None
        if resolved_linkage and os.path.isfile(resolved_linkage):
            linkage_summary = self._inspect_linkage(resolved_linkage, triage_codes_seen)
        elif resolved_linkage:
            linkage_summary = {
                "status": "linkage_file_not_found",
                "provided_path": resolved_linkage,
            }

        extra_meta = {
            "audited_facts_alignment": {
                "expected_total_rows": 143582,
                "observed_total_rows": total_rows,
                "expected_complete_vitals": 91,
                "observed_complete_vitals": complete_vitals_count,
            },
            "binary_urgency_distribution": binary_urgency,
            "critical_status_distribution": critical_status_counts,
            "need_fast_execute_distribution": fast_execute_counts,
        }

        return AggregateDataQuality(
            source_manifest=manifest,
            total_records_inspected=total_rows,
            headers_present=headers_detected,
            missingness_by_field=missingness_by_field,
            vital_distributions=vital_distributions,
            reference_distribution=triage_grades,
            complete_vitals_count=complete_vitals_count,
            complete_vitals_pct=complete_vitals_pct,
            exclusion_summary={},
            linkage_summary=linkage_summary,
            extra_metadata=extra_meta,
        )

    def _inspect_linkage(self, linkage_path: str, primary_codes: Set[str]) -> Dict[str, Any]:
        admission_codes: Set[str] = set()
        total_admission_rows = 0
        with open(linkage_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_admission_rows += 1
                code = str(row.get("triage_code") or row.get("admission_key") or "").strip()
                if code:
                    admission_codes.add(code)

        matched = primary_codes.intersection(admission_codes)
        match_rate_pct = (
            round((len(matched) / len(primary_codes)) * 100.0, 2) if primary_codes else 0.0
        )

        return {
            "status": "linked",
            "linkage_file": os.path.basename(linkage_path),
            "linkage_sha256": compute_file_sha256(linkage_path),
            "total_admission_records": total_admission_rows,
            "unique_admission_keys": len(admission_codes),
            "unique_primary_keys": len(primary_codes),
            "matched_encounter_keys": len(matched),
            "encounter_match_rate_pct": match_rate_pct,
        }

    def load_for_evaluation(
        self, file_path: Optional[str] = None, **kwargs
    ) -> Tuple[List[CanonicalPatientRecord], ExclusionCounters, SourceManifest]:
        """
        STRICT REFUSAL: The Iran ED dataset has published binary ground truth and severe
        vital sparsity, precluding valid 3-tier triage evaluation.
        """
        raise EvaluationRefusedError(EXACT_REFUSAL_MESSAGE)
