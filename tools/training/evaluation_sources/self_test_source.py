"""
Synthetic Self-Test Evaluation Source.

Encapsulates synthetic patient generation and clinical-core rule-based labeling for
harness self-testing (`--self-test`). Proves evaluation machinery without claiming clinical
efficacy (the reference labels come from the very rules engine the model was trained on).
"""

import importlib.util
import os
import sys
import types
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    ExclusionCounters,
    SourceManifest,
    TIER_NAMES,
)

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING_DIR = os.path.abspath(os.path.join(HERE, ".."))


def _load_train_classifier_module():
    if "tree_export" not in sys.modules:
        stub = types.ModuleType("tree_export")
        stub.onnx_to_tree_json = lambda *a, **k: None
        stub.evaluate_tree_json = lambda *a, **k: (None,)
        sys.modules["tree_export"] = stub

    train_path = os.path.join(TRAINING_DIR, "train_classifier.py")
    if not os.path.isfile(train_path):
        raise FileNotFoundError(f"train_classifier.py not found at: {train_path}")

    spec = importlib.util.spec_from_file_location("train_classifier", train_path)
    tc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tc)
    return tc


class SyntheticSelfTestSource(BaseEvaluationSource):
    """
    Self-test evaluation source using synthetic patients and clinical-core labels.
    """

    def __init__(self, n: int = 8000, seed: int = 2026, **kwargs):
        super().__init__(file_path=None, **kwargs)
        self.n = n
        self.seed = seed

    def _build_manifest(self) -> SourceManifest:
        return SourceManifest(
            source_id="synthetic_self_test",
            source_name="Synthetic Self-Test Source (Clinical-Core Rules Reference)",
            version="2026.1 (Synthetic Machinery Check)",
            official_url="Internal Synthetic Generator",
            license_note="VitalNet Internal Test Machinery",
            file_sha256=None,
            input_mode="full_input",
            label_definition="clinical_core_rules_engine (assignTier)",
            scoring_supported=True,
            file_path=None,
            file_size_bytes=None,
        )

    def _generate_data(self) -> Tuple[List[Dict[str, Any]], List[int]]:
        tc = _load_train_classifier_module()
        np.random.seed(self.seed)
        sevs = ["healthy", "mild", "moderate", "severe", "critical"]
        w = [0.30, 0.22, 0.22, 0.16, 0.10]
        formdatas = [
            tc.generate_patient(np.random.choice(sevs, p=w), pediatric=np.random.random() < 0.22)
            for _ in range(self.n)
        ]
        labels = tc.assign_triage_labels(formdatas)
        return formdatas, labels

    def inspect(self, file_path: Optional[str] = None, **kwargs) -> AggregateDataQuality:
        manifest = self._build_manifest()
        formdatas, labels = self._generate_data()

        tier_counts = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
        for lbl in labels:
            t_name = TIER_NAMES.get(int(lbl), "UNKNOWN")
            tier_counts[t_name] = tier_counts.get(t_name, 0) + 1

        vital_fields = ["temperature", "heart_rate", "bp_systolic", "bp_diastolic", "spo2"]
        present_counts = {vf: 0 for vf in vital_fields}
        vital_sums = {vf: 0.0 for vf in vital_fields}
        vital_mins = {vf: float("inf") for vf in vital_fields}
        vital_maxs = {vf: float("-inf") for vf in vital_fields}
        complete_count = 0

        for fd in formdatas:
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
                complete_count += 1

        missingness_by_field: Dict[str, Dict[str, Any]] = {}
        for vf in vital_fields:
            pres = present_counts[vf]
            miss = self.n - pres
            pct = round((miss / self.n) * 100.0, 2) if self.n > 0 else 0.0
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
                    "missingness_pct": missingness_by_field.get(vf, {}).get("missing_pct", 0.0),
                }

        return AggregateDataQuality(
            source_manifest=manifest,
            total_records_inspected=self.n,
            headers_present=list(formdatas[0].keys()) if formdatas else [],
            missingness_by_field=missingness_by_field,
            vital_distributions=vital_distributions,
            reference_distribution=tier_counts,
            complete_vitals_count=complete_count,
            complete_vitals_pct=round((complete_count / self.n) * 100.0, 2) if self.n > 0 else 0.0,
            exclusion_summary={},
            linkage_summary=None,
            extra_metadata={"seed": self.seed, "generated_cohort_size": self.n},
        )

    def load_for_evaluation(
        self, file_path: Optional[str] = None, **kwargs
    ) -> Tuple[List[CanonicalPatientRecord], ExclusionCounters, SourceManifest]:
        manifest = self._build_manifest()
        counters = ExclusionCounters()
        formdatas, labels = self._generate_data()

        records: List[CanonicalPatientRecord] = []
        for idx, (fd, lbl) in enumerate(zip(formdatas, labels), start=1):
            counters.record_total()
            ref_label = TIER_NAMES.get(int(lbl))
            if ref_label is None:
                counters.increment("unusable_reference")
                continue

            record = CanonicalPatientRecord(
                form_data=fd,
                reference_label=ref_label,
                source_row_id=idx,
                is_partial_input=False,
                survey_weight=None,
                raw_fields={},
            )
            counters.record_valid()
            records.append(record)

        return records, counters, manifest
