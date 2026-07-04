"""
Exports a fixed set of synthetic patients + their engineered feature vectors
to backend/tests/fixtures/golden_feature_vectors.json.

This is the ground truth for the Python/JS feature-engineering parity test
(FEATURES_ROADMAP.md §1.2): backend/tests/test_feature_parity.py replays the
Python side, frontend/tests/featureParity.test.mjs replays the JS side
(triageClassifier.js::buildFeatureMap), and both must match this fixture
exactly. If you change clinical_features.py, regenerate this fixture AND
port the equivalent change to triageClassifier.js in the same commit.

Two engineered features (time_of_day_risk, seasonal_risk) are computed from
datetime.now() at inference time — a real, intentional signal (off-hours
short-staffing, seasonal disease patterns), not a bug in the live model. But
it makes a frozen fixture inherently unstable unless generation and both
parity tests all pin the SAME reference instant — see FROZEN_REFERENCE_TIME
below and its twin in test_feature_parity.py / featureParity.test.mjs.
Without this, the fixture silently goes stale as real wall-clock time
crosses an hour/month bucket boundary, and both parity tests start failing
even though Python and JS still agree with each other (verified: this
happened mid-session — both sides drifted from the frozen fixture
identically, confirming it was a test artifact, not a real divergence).

Run: cd backend && python scripts/export_golden_vectors.py
"""
import json
import sys
from datetime import datetime as _real_datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.clinical_features import ClinicalFeatureEngineer  # noqa: E402
from scripts.train_classifier import generate_patient  # noqa: E402

N_PER_SEVERITY = 60
SEVERITIES = ["mild", "moderate", "severe", "critical"]
OUTPUT_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "golden_feature_vectors.json"

# Noon, July 4 — daytime hour bucket (time_of_day_risk == 1.0) and summer
# month bucket (seasonal_risk == 1.2). Must match FROZEN_REFERENCE_TIME in
# test_feature_parity.py and the frozen reference in featureParity.test.mjs.
FROZEN_REFERENCE_TIME = _real_datetime(2026, 7, 4, 12, 0, 0)


class _FrozenDateTime(_real_datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_REFERENCE_TIME.replace(tzinfo=tz)


def main():
    np.random.seed(20260704)  # fixed seed — reproducible fixture
    with patch("app.ml.clinical_features.datetime", _FrozenDateTime):
        engineer = ClinicalFeatureEngineer()
        vectors = []

        for severity in SEVERITIES:
            for _ in range(N_PER_SEVERITY):
                patient = generate_patient(severity, allow_missing=True)
                features = engineer.engineer_features(patient)
                vectors.append({
                    "input": patient,
                    "features": {k: float(v) for k, v in features.items()},
                })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(vectors, f, indent=2, sort_keys=True)

    print(f"Wrote {len(vectors)} golden feature vectors to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
