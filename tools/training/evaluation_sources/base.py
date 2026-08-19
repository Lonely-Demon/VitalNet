"""
Base contracts, manifest models, and abstract source interface for VitalNet's
evaluation sources subsystem.

This module defines the canonical in-memory patient representation, metadata
manifests, exclusion tracking, and data quality containers used to evaluate the
VitalNet triage classifier against external public datasets (or synthetic self-tests)
without patient-level data leakage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple, Union

# Standard 3-tier names in VitalNet
TIER_NAMES = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}
TIER_INDICES = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}


def compute_file_sha256(path: Optional[str], chunk_size: int = 65536) -> Optional[str]:
    """
    Computes the SHA-256 cryptographic checksum of a file in streaming chunks.
    Returns None if path is None, empty, or does not point to an existing file.
    """
    if not path or not os.path.isfile(path):
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class EvaluationRefusedError(Exception):
    """
    Raised when model evaluation / scoring is requested on an external dataset
    that does not support or permit it (e.g. Iran ED binary label structure or
    unsupported 3-tier validation).
    """
    pass


@dataclass
class SourceManifest:
    """
    Metadata describing the provenance, licensing, and schema configuration of an
    evaluation data source.
    """
    source_id: str
    source_name: str
    version: str
    official_url: str
    license_note: str
    file_sha256: Optional[str] = None
    input_mode: str = "full_input"  # "full_input" | "partial_input" | "not_scored"
    label_definition: str = ""
    scoring_supported: bool = True
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "version": self.version,
            "official_url": self.official_url,
            "license_note": self.license_note,
            "file_sha256": self.file_sha256,
            "input_mode": self.input_mode,
            "label_definition": self.label_definition,
            "scoring_supported": self.scoring_supported,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
        }


@dataclass
class ExclusionCounters:
    """
    Tracks record inclusion flow and granular exclusion reasons during cohort filtering.
    """
    total_records: int = 0
    valid_records: int = 0
    excluded_records: int = 0
    reasons: Dict[str, int] = field(default_factory=dict)

    def increment(self, reason: str, count: int = 1) -> None:
        """Increment counter for a specific exclusion reason."""
        self.reasons[reason] = self.reasons.get(reason, 0) + count
        self.excluded_records += count

    def record_valid(self, count: int = 1) -> None:
        """Record valid included encounters."""
        self.valid_records += count

    def record_total(self, count: int = 1) -> None:
        """Record total raw encounters inspected."""
        self.total_records += count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "excluded_records": self.excluded_records,
            "reasons": dict(self.reasons),
        }


@dataclass
class AggregateDataQuality:
    """
    Container for aggregate-only dataset inspection metrics, ensuring ZERO
    patient-level records, individual predictions, or free-text complaints are exposed.
    """
    source_manifest: SourceManifest
    total_records_inspected: int = 0
    headers_present: List[str] = field(default_factory=list)
    missingness_by_field: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    vital_distributions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    reference_distribution: Dict[str, int] = field(default_factory=dict)
    complete_vitals_count: int = 0
    complete_vitals_pct: float = 0.0
    exclusion_summary: Dict[str, int] = field(default_factory=dict)
    linkage_summary: Optional[Dict[str, Any]] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_manifest": self.source_manifest.to_dict(),
            "total_records_inspected": self.total_records_inspected,
            "headers_present": list(self.headers_present),
            "missingness_by_field": self.missingness_by_field,
            "vital_distributions": self.vital_distributions,
            "reference_distribution": self.reference_distribution,
            "complete_vitals_count": self.complete_vitals_count,
            "complete_vitals_pct": self.complete_vitals_pct,
            "exclusion_summary": self.exclusion_summary,
            "linkage_summary": self.linkage_summary,
            "extra_metadata": self.extra_metadata,
        }


@dataclass
class CanonicalPatientRecord:
    """
    In-memory representation of a patient encounter aligned with VitalNet's
    IntakeForm schema and evaluation contracts.
    """
    form_data: Dict[str, Any]
    reference_label: Optional[str] = None  # "ROUTINE", "URGENT", "EMERGENCY", or None
    source_row_id: Union[str, int] = ""
    is_partial_input: bool = False
    survey_weight: Optional[float] = None
    raw_fields: Dict[str, Any] = field(default_factory=dict)

    @property
    def reference_tier_index(self) -> Optional[int]:
        """Returns integer index (0=ROUTINE, 1=URGENT, 2=EMERGENCY) or None."""
        if self.reference_label is None:
            return None
        return TIER_INDICES.get(self.reference_label)


class BaseEvaluationSource(ABC):
    """
    Abstract base class for all evaluation data sources.
    Every source must implement aggregate-only inspection and evaluation loading.
    """

    def __init__(self, file_path: Optional[str] = None, **kwargs):
        self.file_path = file_path
        self.kwargs = kwargs

    def _resolve_file_path(self, override_path: Optional[str] = None) -> Optional[str]:
        return override_path or self.file_path or self.kwargs.get("file_path")

    @abstractmethod
    def inspect(self, file_path: Optional[str] = None, **kwargs) -> AggregateDataQuality:
        """
        Inspect the source file and return aggregate data-quality statistics.
        Guarantees ZERO patient-level data leakage.
        """
        pass

    @abstractmethod
    def load_for_evaluation(
        self, file_path: Optional[str] = None, **kwargs
    ) -> Tuple[List[CanonicalPatientRecord], ExclusionCounters, SourceManifest]:
        """
        Loads the source dataset into canonical patient records for evaluation.

        Returns:
            Tuple of (records, exclusion_counters, source_manifest)

        Raises:
            EvaluationRefusedError: If the source refuses or does not support model scoring.
        """
        pass
