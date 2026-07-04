"""
Guards against Python-side regressions in ClinicalFeatureEngineer AND is half
of the Python/JS parity guarantee (FEATURES_ROADMAP.md §1.2) — the JS half
lives in frontend/tests/featureParity.test.mjs, replaying the same fixture
against triageClassifier.js::buildFeatureMap(). Both must match the fixture
exactly or offline (browser) triage can silently diverge from online triage.
"""
import json
from pathlib import Path

from app.ml.clinical_features import ClinicalFeatureEngineer

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_feature_vectors.json"
TOLERANCE = 1e-6


def test_feature_engineering_matches_golden_vectors():
    vectors = json.loads(FIXTURE_PATH.read_text())
    assert len(vectors) > 0, "golden_feature_vectors.json is empty — regenerate it"

    engineer = ClinicalFeatureEngineer()
    mismatches = []

    for i, vector in enumerate(vectors):
        computed = engineer.engineer_features(vector["input"])
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
