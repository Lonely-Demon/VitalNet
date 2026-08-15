"""
MIMIC-IV-ED Dataset Evaluation Source (Gate 2: Credentialed Benchmark).

This module implements the adapter for MIMIC-IV-ED v2.2 (Beth Israel Deaconess Medical Center,
~425k ED stays, 2011-2019) linked with MIMIC-IV core patient demographics.

Official Source References:
- Documentation & DOI: https://doi.org/10.13026/5ntk-km72
- Dataset Portal: https://physionet.org/content/mimic-iv-ed/2.2/
- MIMIC-IV Core: https://physionet.org/content/mimiciv/2.2/

Enforces:
- Exact source precedence: edstays.gender (stay-level sex), patients.anchor_age (patient-level age).
- Preservation of HIPAA Safe Harbor anchor_age top-coding (integer 91 represents age >= 89).
- Hard rejection of prohibited tables (diagnosis, pyxis, vitalsign, disposition, admission, outcomes).
- Pre-canonicalization stripping of prohibited fields (hadm_id, outtime, disposition, los, dod, anchor_year).
- Pre-registered primary mapping mimic_esi_v1 (1-2 -> EMERGENCY, 3 -> URGENT, 4-5 -> ROUTINE).
- Pre-registered cohort policies: all_stays (primary) and first_stay_only (sensitivity).
- Strict triage-time input arm (mimic_triage_contract_v1); hard-disabled medication arm (mimic_full_available_context_v1).
- Exact Fahrenheit-to-Celsius temperature conversion with plausibility filtering.
- Rejection of Doppler codes (998) and blood pressure inversion (sbp <= dbp).
- Strict isolation of resprate and pain from model input (recorded in inspection metadata only).
- Gate M4 staged scoring refusal contract: scoring refused by default; internal test-only synthetic mode.
- Strict zero patient-level data leakage guaranteed in all reports and metadata containers.
"""

import csv
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .base import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    ExclusionCounters,
    SourceManifest,
    compute_file_sha256,
)
from .mimic_symptom_parser import (
    PARSER_VERSION,
    StreamingSymptomCoverageAccumulator,
    compute_symptom_parser_coverage,
    parse_symptoms_from_complaint,
)

# Pre-registered 5-to-3 tier ESI mapping
MIMIC_ESI_V1: Dict[int, str] = {
    1: "EMERGENCY",
    2: "EMERGENCY",
    3: "URGENT",
    4: "ROUTINE",
    5: "ROUTINE",
}

# Pre-registered cohort policies
COHORT_POLICY_ALL_STAYS: str = "all_stays"
COHORT_POLICY_FIRST_STAY_ONLY: str = "first_stay_only"
VALID_COHORT_POLICIES: Set[str] = {COHORT_POLICY_ALL_STAYS, COHORT_POLICY_FIRST_STAY_ONLY}

# Input arms
ARM_TRIAGE_CONTRACT: str = "mimic_triage_contract_v1"
ARM_FULL_CONTEXT: str = "mimic_full_available_context_v1"

# Prohibited tables and fields (Strict temporal leakage prevention)
PROHIBITED_TABLE_NAMES: Tuple[str, ...] = (
    "diagnosis",
    "pyxis",
    "vitalsign",
    "disposition",
    "admission",
    "outcomes",
)

PROHIBITED_FIELD_NAMES: Tuple[str, ...] = (
    "hadm_id",
    "outtime",
    "disposition",
    "length_of_stay",
    "los",
    "dod",
    "anchor_year",
    "anchor_year_group",
)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "nan", "n/a", "-9", "-8", "?"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    f = _safe_float(val)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, TypeError):
        return None


class MIMICIVEDSource(BaseEvaluationSource):
    """
    Adapter for MIMIC-IV-ED v2.2 with linked MIMIC-IV core demographics (Gate 2).
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        patients_file_path: Optional[str] = None,
        edstays_file_path: Optional[str] = None,
        medrecon_file_path: Optional[str] = None,
        input_mode: str = ARM_TRIAGE_CONTRACT,
        cohort_policy: str = COHORT_POLICY_ALL_STAYS,
        gate_m4_authorized: bool = False,
        gate_medrecon_temporal_authorized: bool = False,
        exploratory_medrecon_inspection: bool = False,
        _synthetic_test_mode: bool = False,
        **kwargs,
    ):
        super().__init__(file_path=file_path, **kwargs)
        self.patients_file_path = patients_file_path or kwargs.get("patients_file")
        self.edstays_file_path = edstays_file_path or kwargs.get("edstays_file")
        self.medrecon_file_path = medrecon_file_path or kwargs.get("medrecon_file")
        self.input_mode = input_mode or ARM_TRIAGE_CONTRACT
        self.cohort_policy = cohort_policy or COHORT_POLICY_ALL_STAYS
        self.gate_m4_authorized = gate_m4_authorized
        self.gate_medrecon_temporal_authorized = gate_medrecon_temporal_authorized
        self.exploratory_medrecon_inspection = exploratory_medrecon_inspection
        self._synthetic_test_mode = _synthetic_test_mode

        if self.cohort_policy not in VALID_COHORT_POLICIES:
            raise ValueError(
                f"Invalid cohort policy: '{self.cohort_policy}'. Must be one of: {VALID_COHORT_POLICIES}"
            )

        if self.exploratory_medrecon_inspection and not self.gate_medrecon_temporal_authorized:
            raise EvaluationRefusedError(
                "Exploratory medrecon inspection is hard-disabled pending independent "
                "temporal-eligibility review and separate temporal authorization. "
                "Gate M4 authorization alone cannot unlock medrecon operations."
            )

        # Prohibited table validation across paths and kwargs
        all_passed_paths = [
            self.file_path,
            self.patients_file_path,
            self.edstays_file_path,
            self.medrecon_file_path,
        ] + [str(v) for v in kwargs.values() if isinstance(v, str)]

        for p in all_passed_paths:
            if p:
                basename = os.path.basename(p).lower()
                for prohibited in PROHIBITED_TABLE_NAMES:
                    if prohibited in basename:
                        raise ValueError(
                            f"Prohibited table '{prohibited}' detected in path: '{p}'. "
                            f"Downstream and post-triage tables ({PROHIBITED_TABLE_NAMES}) are strictly rejected."
                        )

        # Internal synthetic test mode restriction
        if self._synthetic_test_mode:
            self._verify_synthetic_fixtures_only(all_passed_paths)

    def _verify_synthetic_fixtures_only(self, paths: List[Optional[str]]) -> None:
        """Verifies that internal synthetic test mode is never executed on non-fixture paths."""
        for p in paths:
            if p:
                norm = os.path.abspath(p).replace("\\", "/").lower()
                if "tests/fixtures" not in norm and "synthetic" not in norm:
                    raise ValueError(
                        f"synthetic_test_mode is strictly restricted to approved synthetic fixtures. "
                        f"Attempted to execute on non-fixture path: '{p}'."
                    )

    def _build_manifest(self, path: Optional[str]) -> SourceManifest:
        sha256 = compute_file_sha256(path) if path else None
        size_bytes = os.path.getsize(path) if path and os.path.isfile(path) else None
        return SourceManifest(
            source_id="mimic_iv_ed",
            source_name="MIMIC-IV-ED v2.2 (Beth Israel Deaconess Medical Center Emergency Department)",
            version="v2.2",
            official_url="https://physionet.org/content/mimic-iv-ed/2.2/",
            license_note="PhysioNet Credentialed Health Data Use Agreement (100% de-identified)",
            file_sha256=sha256,
            input_mode=self.input_mode,
            label_definition="mimic_esi_v1 (1-2 -> EMERGENCY, 3 -> URGENT, 4-5 -> ROUTINE)",
            scoring_supported=True,
            file_path=path,
            file_size_bytes=size_bytes,
        )

    def _load_patients_demographics(self, path: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """Loads anchor_age and gender from patients.csv keyed by subject_id."""
        patients_map: Dict[str, Dict[str, Any]] = {}
        if not path or not os.path.isfile(path):
            return patients_map

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sub_id = str(row.get("subject_id", "")).strip()
                if not sub_id:
                    continue
                # Anchor age directly; top-coded integer 91 preserved
                age_val = _safe_int(row.get("anchor_age"))
                raw_gender = str(row.get("gender", "")).strip()
                patients_map[sub_id] = {
                    "anchor_age": age_val,
                    "gender": raw_gender,
                }
        return patients_map

    def _load_edstays_metadata(self, path: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """Loads stay-level metadata (gender, intime) keyed by stay_id."""
        stays_map: Dict[str, Dict[str, Any]] = {}
        if not path or not os.path.isfile(path):
            return stays_map

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stay_id = str(row.get("stay_id", "")).strip()
                if not stay_id:
                    continue
                sub_id = str(row.get("subject_id", "")).strip()
                raw_gender = str(row.get("gender", "")).strip()
                intime = str(row.get("intime", "")).strip()
                stays_map[stay_id] = {
                    "subject_id": sub_id,
                    "gender": raw_gender,
                    "intime": intime,
                }
        return stays_map

    def inspect(
        self,
        file_path: Optional[str] = None,
        patients_file_path: Optional[str] = None,
        edstays_file_path: Optional[str] = None,
        medrecon_file_path: Optional[str] = None,
        **kwargs,
    ) -> AggregateDataQuality:
        """
        Performs aggregate-only data quality inspection across MIMIC triage and linkage files.
        Strictly guarantees ZERO patient-level records, identifiers, or free-text complaints are exposed.
        """
        resolved_triage = self._resolve_file_path(file_path)
        if not resolved_triage or not os.path.isfile(resolved_triage):
            raise FileNotFoundError(f"MIMIC-IV-ED triage file not found: {resolved_triage}")

        resolved_patients = patients_file_path or self.patients_file_path or kwargs.get("patients_file")
        resolved_edstays = edstays_file_path or self.edstays_file_path or kwargs.get("edstays_file")
        resolved_medrecon = medrecon_file_path or self.medrecon_file_path or kwargs.get("medrecon_file")

        if (
            self.exploratory_medrecon_inspection
            or kwargs.get("exploratory_medrecon_inspection")
        ) and not self.gate_medrecon_temporal_authorized:
            raise EvaluationRefusedError(
                "Exploratory medrecon inspection is hard-disabled pending independent "
                "temporal-eligibility review and separate temporal authorization. "
                "Gate M4 authorization alone cannot unlock medrecon operations."
            )

        manifest = self._build_manifest(resolved_triage)

        patients_map = self._load_patients_demographics(resolved_patients)
        edstays_map = self._load_edstays_metadata(resolved_edstays)

        total_rows = 0
        headers_present: List[str] = []
        parser_accumulator = StreamingSymptomCoverageAccumulator()
        subject_encounter_counts: Dict[str, int] = {}
        unique_stay_ids: Set[str] = set()

        missing_counts: Dict[str, int] = {
            "temperature": 0,
            "heartrate": 0,
            "resprate": 0,
            "o2sat": 0,
            "sbp": 0,
            "dbp": 0,
            "pain": 0,
            "acuity": 0,
            "chiefcomplaint": 0,
            "anchor_age": 0,
            "gender": 0,
        }
        valid_counts: Dict[str, int] = {k: 0 for k in missing_counts}

        vital_sums: Dict[str, float] = {}
        vital_mins: Dict[str, float] = {}
        vital_maxs: Dict[str, float] = {}

        acuity_distribution: Dict[str, int] = {
            "1_EMERGENCY": 0,
            "2_EMERGENCY": 0,
            "3_URGENT": 0,
            "4_ROUTINE": 0,
            "5_ROUTINE": 0,
            "unmapped_or_missing": 0,
        }

        five_vital_complete_count = 0
        gender_conflict_count = 0
        unlinked_patients_count = 0
        unlinked_edstays_count = 0
        bp_inversion_count = 0
        age_top_coded_count = 0

        exclusion_summary: Dict[str, int] = {
            "missing_age_linkage": 0,
            "invalid_or_missing_acuity": 0,
            "invalid_sex": 0,
            "invalid_bp_inversion": 0,
            "temp_out_of_plausible_range": 0,
            "hr_out_of_plausible_range": 0,
            "sbp_out_of_plausible_range": 0,
            "dbp_out_of_plausible_range": 0,
            "spo2_out_of_plausible_range": 0,
        }

        with open(resolved_triage, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                headers_present = list(reader.fieldnames)

            for row in reader:
                total_rows += 1
                stay_id = str(row.get("stay_id", "")).strip()
                sub_id = str(row.get("subject_id", "")).strip()

                if stay_id:
                    unique_stay_ids.add(stay_id)
                if sub_id:
                    subject_encounter_counts[sub_id] = subject_encounter_counts.get(sub_id, 0) + 1

                # 1. Age Linkage
                p_info = patients_map.get(sub_id) if sub_id else None
                if not p_info or p_info.get("anchor_age") is None:
                    missing_counts["anchor_age"] += 1
                    unlinked_patients_count += 1
                    exclusion_summary["missing_age_linkage"] += 1
                    patient_age = None
                else:
                    patient_age = p_info["anchor_age"]
                    valid_counts["anchor_age"] += 1
                    if patient_age == 91:
                        age_top_coded_count += 1

                # 2. Sex Precedence & Conflict Check
                stay_info = edstays_map.get(stay_id) if stay_id else None
                stay_gender = stay_info.get("gender") if stay_info else None
                patient_gender = p_info.get("gender") if p_info else None

                if not stay_info:
                    unlinked_edstays_count += 1

                if stay_gender and patient_gender:
                    sg_norm = stay_gender.strip().lower()
                    pg_norm = patient_gender.strip().lower()
                    if sg_norm and pg_norm and sg_norm[0] != pg_norm[0]:
                        gender_conflict_count += 1

                resolved_gender = stay_gender or patient_gender
                if resolved_gender and resolved_gender.strip():
                    valid_counts["gender"] += 1
                else:
                    missing_counts["gender"] += 1

                # 3. Vitals Extraction & Plausibility
                # Temperature (°F -> °C)
                raw_temp = _safe_float(row.get("temperature"))
                temp_c: Optional[float] = None
                if raw_temp is not None:
                    if 80.0 <= raw_temp <= 110.0:
                        temp_c = round((raw_temp - 32.0) * 5.0 / 9.0, 1)
                        valid_counts["temperature"] += 1
                    else:
                        missing_counts["temperature"] += 1
                        exclusion_summary["temp_out_of_plausible_range"] += 1
                else:
                    missing_counts["temperature"] += 1

                # Heart Rate
                raw_hr = _safe_int(row.get("heartrate"))
                hr: Optional[int] = None
                if raw_hr is not None:
                    if 0 <= raw_hr <= 240 and raw_hr != 998:
                        hr = raw_hr
                        valid_counts["heartrate"] += 1
                    else:
                        missing_counts["heartrate"] += 1
                        exclusion_summary["hr_out_of_plausible_range"] += 1
                else:
                    missing_counts["heartrate"] += 1

                # SBP
                raw_sbp = _safe_int(row.get("sbp"))
                sbp: Optional[int] = None
                if raw_sbp is not None:
                    if 40 <= raw_sbp <= 290 and raw_sbp != 998:
                        sbp = raw_sbp
                        valid_counts["sbp"] += 1
                    else:
                        missing_counts["sbp"] += 1
                        exclusion_summary["sbp_out_of_plausible_range"] += 1
                else:
                    missing_counts["sbp"] += 1

                # DBP
                raw_dbp = _safe_int(row.get("dbp"))
                dbp: Optional[int] = None
                if raw_dbp is not None:
                    if 20 <= raw_dbp <= 190 and raw_dbp != 998:
                        dbp = raw_dbp
                        valid_counts["dbp"] += 1
                    else:
                        missing_counts["dbp"] += 1
                        exclusion_summary["dbp_out_of_plausible_range"] += 1
                else:
                    missing_counts["dbp"] += 1

                # BP Inversion
                if sbp is not None and dbp is not None:
                    if sbp <= dbp:
                        bp_inversion_count += 1
                        exclusion_summary["invalid_bp_inversion"] += 1
                        sbp = None
                        dbp = None

                # SpO2
                raw_o2 = _safe_int(row.get("o2sat"))
                spo2: Optional[int] = None
                if raw_o2 is not None:
                    if 0 <= raw_o2 <= 100:
                        spo2 = raw_o2
                        valid_counts["o2sat"] += 1
                    else:
                        missing_counts["o2sat"] += 1
                        exclusion_summary["spo2_out_of_plausible_range"] += 1
                else:
                    missing_counts["o2sat"] += 1

                # Respiratory Rate (Inspection metadata only!)
                raw_rr = _safe_int(row.get("resprate"))
                if raw_rr is not None and 0 <= raw_rr <= 150:
                    valid_counts["resprate"] += 1
                else:
                    missing_counts["resprate"] += 1

                # Pain (Inspection metadata only!)
                raw_pain = str(row.get("pain", "")).strip()
                if raw_pain and raw_pain.lower() not in ("null", "none", "nan", "n/a", "?"):
                    valid_counts["pain"] += 1
                else:
                    missing_counts["pain"] += 1

                # 5-Vital completeness
                if (
                    temp_c is not None
                    and hr is not None
                    and sbp is not None
                    and dbp is not None
                    and spo2 is not None
                ):
                    five_vital_complete_count += 1

                # Track numerical vital distributions
                for vname, vval in [
                    ("temperature_c", temp_c),
                    ("heartrate", hr),
                    ("sbp", sbp),
                    ("dbp", dbp),
                    ("o2sat", spo2),
                    ("resprate", raw_rr if (raw_rr is not None and 0 <= raw_rr <= 150) else None),
                ]:
                    if vval is not None:
                        val_flt = float(vval)
                        vital_sums[vname] = vital_sums.get(vname, 0.0) + val_flt
                        vital_mins[vname] = (
                            min(vital_mins[vname], val_flt) if vname in vital_mins else val_flt
                        )
                        vital_maxs[vname] = (
                            max(vital_maxs[vname], val_flt) if vname in vital_maxs else val_flt
                        )

                # 4. Chief Complaint (streamed into aggregate accumulator; raw complaint is never retained)
                raw_comp = row.get("chiefcomplaint")
                parser_accumulator.update(raw_comp)
                if raw_comp and str(raw_comp).strip():
                    valid_counts["chiefcomplaint"] += 1
                else:
                    missing_counts["chiefcomplaint"] += 1

                # 5. Acuity (ESI 1-5)
                acuity_int = _safe_int(row.get("acuity"))
                if acuity_int in MIMIC_ESI_V1:
                    valid_counts["acuity"] += 1
                    tier_label = MIMIC_ESI_V1[acuity_int]
                    acuity_key = f"{acuity_int}_{tier_label}"
                    acuity_distribution[acuity_key] = acuity_distribution.get(acuity_key, 0) + 1
                else:
                    missing_counts["acuity"] += 1
                    acuity_distribution["unmapped_or_missing"] += 1
                    exclusion_summary["invalid_or_missing_acuity"] += 1

        # Calculate vital distributions
        vital_distributions: Dict[str, Dict[str, Any]] = {}
        for vname in ["temperature_c", "heartrate", "sbp", "dbp", "o2sat", "resprate"]:
            field_key = "temperature" if vname == "temperature_c" else vname
            v_cnt = valid_counts.get(field_key, 0)
            if v_cnt > 0:
                vital_distributions[vname] = {
                    "valid_count": v_cnt,
                    "mean": round(vital_sums[vname] / v_cnt, 2),
                    "min": round(vital_mins[vname], 1),
                    "max": round(vital_maxs[vname], 1),
                    "missingness_pct": round((total_rows - v_cnt) / total_rows * 100.0, 2)
                    if total_rows > 0
                    else 0.0,
                }
            else:
                vital_distributions[vname] = {
                    "valid_count": 0,
                    "mean": None,
                    "min": None,
                    "max": None,
                    "missingness_pct": 100.0,
                }

        # Calculate field missingness map
        missingness_by_field: Dict[str, Dict[str, Any]] = {}
        for fld, m_cnt in missing_counts.items():
            v_cnt = valid_counts[fld]
            m_pct = round((m_cnt / total_rows * 100.0), 2) if total_rows > 0 else 0.0
            missingness_by_field[fld] = {
                "missing_count": m_cnt,
                "valid_count": v_cnt,
                "missing_pct": m_pct,
            }

        # Finalize streaming symptom parser coverage (aggregate-only)
        parser_coverage = parser_accumulator.finalize()

        # Subject repetition statistics
        unique_subject_count = len(subject_encounter_counts)
        encounters_per_subject = list(subject_encounter_counts.values())
        mean_visits = (
            round(sum(encounters_per_subject) / unique_subject_count, 2)
            if unique_subject_count > 0
            else 0.0
        )
        max_visits = max(encounters_per_subject) if encounters_per_subject else 0
        repeated_subjects_count = sum(1 for c in encounters_per_subject if c > 1)

        # Medrecon inspection note - primary triage contract inspection strictly ignores medrecon
        medrecon_ignored_note = False
        if resolved_medrecon:
            medrecon_ignored_note = True

        linkage_summary = {
            "patients_linked_file": os.path.basename(resolved_patients) if resolved_patients else None,
            "edstays_linked_file": os.path.basename(resolved_edstays) if resolved_edstays else None,
            "total_encounters_inspected": total_rows,
            "unique_stay_ids": len(unique_stay_ids),
            "unique_subject_ids": unique_subject_count,
            "mean_encounters_per_subject": mean_visits,
            "max_encounters_single_subject": max_visits,
            "repeated_subject_count": repeated_subjects_count,
            "gender_conflict_count": gender_conflict_count,
            "unlinked_patients_count": unlinked_patients_count,
            "unlinked_edstays_count": unlinked_edstays_count,
            "anchor_age_top_coded_count": age_top_coded_count,
            "medrecon_file_ignored_in_primary_mode": medrecon_ignored_note,
        }

        five_vital_pct = (
            round(five_vital_complete_count / total_rows * 100.0, 2) if total_rows > 0 else 0.0
        )

        return AggregateDataQuality(
            source_manifest=manifest,
            total_records_inspected=total_rows,
            headers_present=headers_present,
            missingness_by_field=missingness_by_field,
            vital_distributions=vital_distributions,
            reference_distribution=acuity_distribution,
            complete_vitals_count=five_vital_complete_count,
            complete_vitals_pct=five_vital_pct,
            exclusion_summary=exclusion_summary,
            linkage_summary=linkage_summary,
            extra_metadata={
                "parser_version": PARSER_VERSION,
                "parser_coverage": parser_coverage,
                "cohort_policy": self.cohort_policy,
                "input_mode": self.input_mode,
                "bp_inversion_count": bp_inversion_count,
            },
        )

    def load_for_evaluation(
        self,
        file_path: Optional[str] = None,
        patients_file_path: Optional[str] = None,
        edstays_file_path: Optional[str] = None,
        **kwargs,
    ) -> Tuple[List[CanonicalPatientRecord], ExclusionCounters, SourceManifest]:
        """
        Loads MIMIC-IV-ED records into canonical patient representations for triage evaluation.

        Enforces:
        - Refuses scoring unless Gate M4 explicit authorization or internal test-only synthetic mode is active.
        - Hard-refuses mimic_full_available_context_v1 arm unless separate temporal authorization is supplied.
        - Strict pre-registered cohort policy (all_stays vs first_stay_only).
        - Deterministic sex precedence (edstays.gender primary, patients.gender fallback).
        - Explicit exclusion accounting for unlinked age, invalid acuity, sex, and inverted BP.
        """
        # Hard-disabled medication context arm check
        if self.input_mode == ARM_FULL_CONTEXT:
            if not self.gate_medrecon_temporal_authorized:
                raise EvaluationRefusedError(
                    "mimic_full_available_context_v1 is hard-disabled pending independent "
                    "temporal-eligibility review and separate authorization."
                )

        # Gate M4 Staged Scoring Refusal Guard
        if not (self.gate_m4_authorized or self._synthetic_test_mode):
            raise EvaluationRefusedError(
                "MIMIC-IV-ED scoring is blocked pending Gate M4 explicit authorization. "
                "Use inspection mode (--inspect-source mimic-iv-ed) or pass --gate-m4-authorized "
                "after completing Gates M0-M3."
            )

        resolved_triage = self._resolve_file_path(file_path)
        if not resolved_triage or not os.path.isfile(resolved_triage):
            raise FileNotFoundError(f"MIMIC-IV-ED triage file not found: {resolved_triage}")

        resolved_patients = patients_file_path or self.patients_file_path or kwargs.get("patients_file")
        resolved_edstays = edstays_file_path or self.edstays_file_path or kwargs.get("edstays_file")

        manifest = self._build_manifest(resolved_triage)
        counters = ExclusionCounters()

        patients_map = self._load_patients_demographics(resolved_patients)
        edstays_map = self._load_edstays_metadata(resolved_edstays)

        records: List[CanonicalPatientRecord] = []
        seen_subjects: Set[str] = set()

        with open(resolved_triage, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for line_idx, row in enumerate(reader, start=1):
                counters.record_total()

                # Pre-canonicalization stripping: strictly drop prohibited fields
                clean_row = {
                    k: v
                    for k, v in row.items()
                    if k.lower() not in PROHIBITED_FIELD_NAMES
                }

                stay_id = str(clean_row.get("stay_id", "")).strip()
                sub_id = str(clean_row.get("subject_id", "")).strip()

                # Cohort Policy Handling (first_stay_only deduplication)
                if self.cohort_policy == COHORT_POLICY_FIRST_STAY_ONLY:
                    if sub_id in seen_subjects:
                        counters.increment("duplicate_subject_excluded")
                        continue
                    if sub_id:
                        seen_subjects.add(sub_id)

                # 1. Reference Acuity Mapping
                acuity_int = _safe_int(clean_row.get("acuity"))
                if acuity_int not in MIMIC_ESI_V1:
                    counters.increment("invalid_or_missing_acuity")
                    continue
                reference_label = MIMIC_ESI_V1[acuity_int]

                # 2. Age Linkage
                p_info = patients_map.get(sub_id) if sub_id else None
                if not p_info or p_info.get("anchor_age") is None:
                    counters.increment("missing_age_linkage")
                    continue
                patient_age = p_info["anchor_age"]

                # 3. Sex Precedence
                stay_info = edstays_map.get(stay_id) if stay_id else None
                stay_gender = stay_info.get("gender") if stay_info else None
                patient_gender = p_info.get("gender") if p_info else None

                raw_sex = stay_gender or patient_gender
                if not raw_sex:
                    counters.increment("invalid_sex")
                    continue

                sex_clean = raw_sex.strip().lower()
                if sex_clean in ("f", "female", "1"):
                    patient_sex = "female"
                elif sex_clean in ("m", "male", "2"):
                    patient_sex = "male"
                else:
                    counters.increment("invalid_sex")
                    continue

                # 4. Vitals Conversion and Plausibility
                # Temperature (°F -> °C)
                raw_temp = _safe_float(clean_row.get("temperature"))
                temperature: Optional[float] = None
                if raw_temp is not None:
                    if 80.0 <= raw_temp <= 110.0:
                        temperature = round((raw_temp - 32.0) * 5.0 / 9.0, 1)
                    else:
                        counters.increment("temp_out_of_plausible_range")

                # Heart Rate
                raw_hr = _safe_int(clean_row.get("heartrate"))
                heart_rate: Optional[int] = None
                if raw_hr is not None:
                    if 0 <= raw_hr <= 240 and raw_hr != 998:
                        heart_rate = raw_hr
                    else:
                        counters.increment("hr_out_of_plausible_range")

                # SBP
                raw_sbp = _safe_int(clean_row.get("sbp"))
                bp_systolic: Optional[int] = None
                if raw_sbp is not None:
                    if 40 <= raw_sbp <= 290 and raw_sbp != 998:
                        bp_systolic = raw_sbp
                    else:
                        counters.increment("sbp_out_of_plausible_range")

                # DBP
                raw_dbp = _safe_int(clean_row.get("dbp"))
                bp_diastolic: Optional[int] = None
                if raw_dbp is not None:
                    if 20 <= raw_dbp <= 190 and raw_dbp != 998:
                        bp_diastolic = raw_dbp
                    else:
                        counters.increment("dbp_out_of_plausible_range")

                # BP Inversion
                if bp_systolic is not None and bp_diastolic is not None:
                    if bp_systolic <= bp_diastolic:
                        counters.increment("invalid_bp_inversion")
                        bp_systolic = None
                        bp_diastolic = None

                # SpO2
                raw_o2 = _safe_int(clean_row.get("o2sat"))
                spo2: Optional[int] = None
                if raw_o2 is not None:
                    if 0 <= raw_o2 <= 100:
                        spo2 = raw_o2
                    else:
                        counters.increment("spo2_out_of_plausible_range")

                # 5. Chief Complaint & Deterministic Symptoms Parsing
                raw_complaint = clean_row.get("chiefcomplaint")
                complaint_str = str(raw_complaint).strip() if raw_complaint else ""
                parsed_symptoms = parse_symptoms_from_complaint(complaint_str)

                # Form Data matching VitalNet IntakeForm contract
                form_data: Dict[str, Any] = {
                    "patient_age": patient_age,
                    "patient_sex": patient_sex,
                    "bp_systolic": bp_systolic,
                    "bp_diastolic": bp_diastolic,
                    "spo2": spo2,
                    "heart_rate": heart_rate,
                    "temperature": temperature,
                    "symptoms": parsed_symptoms,
                    "chief_complaint": complaint_str,
                    # Explicit uninvented ASHA placeholders
                    "complaint_duration": "",
                    "location": "",
                    "known_conditions": "",
                    "current_medications": "",
                    "is_pregnant": None,
                    "observations": "",
                }

                # Safe metadata raw_fields strictly purged of prohibited identifiers and post-triage fields
                safe_raw_fields: Dict[str, Any] = {
                    "raw_acuity": clean_row.get("acuity"),
                    "resprate": _safe_int(clean_row.get("resprate")),
                    "pain": str(clean_row.get("pain", "")).strip(),
                }

                record = CanonicalPatientRecord(
                    form_data=form_data,
                    reference_label=reference_label,
                    source_row_id=stay_id or line_idx,
                    is_partial_input=False,
                    survey_weight=None,
                    raw_fields=safe_raw_fields,
                )

                records.append(record)
                counters.record_valid()

        return records, counters, manifest
