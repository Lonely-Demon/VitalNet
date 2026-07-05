"""
Guards against Python-side regressions in ClinicalFeatureEngineer AND is half
of the Python/JS parity guarantee (FEATURES_ROADMAP.md §1.2) — the JS half
lives in frontend/tests/featureParity.test.mjs, replaying the same fixture
against triageClassifier.js::buildFeatureMap(). Both must match the fixture
exactly or offline (browser) triage can silently diverge from online triage.

Every fixture input carries an explicit _reference_month (set by
scripts/train_classifier.py::generate_patient), so seasonal_risk no longer
depends on real wall-clock time for these vectors — but this test still
freezes datetime.now() (matching scripts/export_golden_vectors.py and
featureParity.test.mjs's JS-side reference) as a defensive fallback for any
future contextual feature that reads it directly, and to guard against a
regression that silently drops _reference_month from the fixture.
"""
import json
from datetime import datetime as _real_datetime
from pathlib import Path
from unittest.mock import patch

from app.ml.clinical_features import ClinicalFeatureEngineer

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_feature_vectors.json"
TOLERANCE = 1e-6

# Must match scripts/export_golden_vectors.py's FROZEN_REFERENCE_TIME exactly.
FROZEN_REFERENCE_TIME = _real_datetime(2026, 7, 4, 12, 0, 0)


class _FrozenDateTime(_real_datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_REFERENCE_TIME.replace(tzinfo=tz)


def test_feature_engineering_matches_golden_vectors():
    vectors = json.loads(FIXTURE_PATH.read_text())
    assert len(vectors) > 0, "golden_feature_vectors.json is empty — regenerate it"

    mismatches = []

    with patch("app.ml.clinical_features.datetime", _FrozenDateTime):
        engineer = ClinicalFeatureEngineer()
        computed_vectors = [engineer.engineer_features(vector["input"]) for vector in vectors]

    for i, (vector, computed) in enumerate(zip(vectors, computed_vectors)):
        expected = vector["features"]

        if set(computed.keys()) != set(expected.keys()):
            mismatches.append(
                f"vector {i}: feature key mismatch — "
                f"missing={set(expected) - set(computed)}, extra={set(computed) - set(expected)}"
            )
            continue

        for key, expected_val in expected.items():
            computed_val = computed[key]
            if abs(computed_val - expected_val) > TOLERANCE:
                mismatches.append(
                    f"vector {i}, feature '{key}': expected {expected_val}, got {computed_val}"
                )

    assert not mismatches, (
        "ClinicalFeatureEngineer output drifted from the golden fixture "
        f"({len(mismatches)} mismatches). If this is an intentional change, "
        "regenerate the fixture: python scripts/export_golden_vectors.py "
        "— and mirror the change in frontend/src/utils/triageClassifier.js.\n"
        + "\n".join(mismatches[:20])
    )
