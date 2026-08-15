"""
VitalNet Modular Evaluation Sources Package.

Provides standardized dataset adapters, fixed-width parsers, schema mappers,
and aggregate-only inspection containers for external validation and self-testing.
"""

from typing import Optional

from .base import (
    AggregateDataQuality,
    BaseEvaluationSource,
    CanonicalPatientRecord,
    EvaluationRefusedError,
    ExclusionCounters,
    SourceManifest,
    TIER_INDICES,
    TIER_NAMES,
    compute_file_sha256,
)
from .generic_csv import (
    ACUITY_MAPS,
    ALLOWED_SYMPTOMS,
    GenericCSVSource,
    parse_reference_tier,
    row_to_formdata,
)
from .iran_ed import (
    EXACT_REFUSAL_MESSAGE,
    PUBLISHED_HEADERS,
    IranEDSource,
)
from .nhamcs_2022 import (
    NHAMCS_IMMEDIACY_V1,
    NHAMCS2022Source,
)
from .self_test_source import SyntheticSelfTestSource

__all__ = [
    "AggregateDataQuality",
    "BaseEvaluationSource",
    "CanonicalPatientRecord",
    "EvaluationRefusedError",
    "ExclusionCounters",
    "SourceManifest",
    "TIER_INDICES",
    "TIER_NAMES",
    "compute_file_sha256",
    "IranEDSource",
    "PUBLISHED_HEADERS",
    "EXACT_REFUSAL_MESSAGE",
    "NHAMCS2022Source",
    "NHAMCS_IMMEDIACY_V1",
    "GenericCSVSource",
    "ACUITY_MAPS",
    "ALLOWED_SYMPTOMS",
    "parse_reference_tier",
    "row_to_formdata",
    "SyntheticSelfTestSource",
    "get_evaluation_source",
]


def get_evaluation_source(
    source_id: str, file_path: Optional[str] = None, **kwargs
) -> BaseEvaluationSource:
    """
    Factory function to instantiate an evaluation source adapter by name/identifier.
    """
    normalized_id = source_id.lower().replace("-", "_").strip()

    if normalized_id in ("iran_ed", "iran"):
        return IranEDSource(file_path=file_path, **kwargs)
    elif normalized_id in ("nhamcs_2022", "nhamcs", "cdc_nhamcs", "ed2022"):
        return NHAMCS2022Source(file_path=file_path, **kwargs)
    elif normalized_id in ("generic_csv", "csv"):
        return GenericCSVSource(file_path=file_path, **kwargs)
    elif normalized_id in ("synthetic_self_test", "self_test", "synthetic"):
        return SyntheticSelfTestSource(**kwargs)
    else:
        raise ValueError(
            f"Unknown evaluation source: '{source_id}'. "
            f"Available sources: iran-ed, nhamcs-2022, generic-csv, self-test."
        )
