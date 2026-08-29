"""
Exports a fixed set of synthetic patients + their engineered feature vectors
to backend/tests/fixtures/golden_feature_vectors.json.

This is a regression snapshot for the legacy FastAPI backend's OWN
ClinicalFeatureEngineer (backend/tests/test_feature_parity.py replays it
against this fixture). It is no longer a cross-language parity check —
since the Round 6 TypeScript migration (docs/DECISIONS.md §33),
ClinicalFeatureEngineer is not mirrored anywhere else; the authoritative
feature engineering is packages/clinical-core/src/features.ts, which has
its own, independently-sourced golden fixture (see
tools/training/train_classifier.py's FEATURE_GOLDEN_PATH step). This
script and the fixture it produces exist only as long as backend/app/ does
— they are slated for removal together at the deferred FastAPI cutover.

generate_patient() sets an explicit _reference_month on every synthetic
patient (docs/DECISIONS.md §23), so seasonal_risk no longer depends on real
wall-clock time for these vectors. FROZEN_REFERENCE_TIME below is kept as a
defensive fallback for any other contextual feature that might read
datetime.now() directly, matching test_feature_parity.py.

Run: cd tools/training && python export_golden_vectors.py
"""
import json
import os
import sys
from datetime import datetime as _real_datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.dirname(__file__))

from app.ml.clinical_features import ClinicalFeatureEngineer  # noqa: E402
from train_classifier import generate_patient  # noqa: E402

N_PER_SEVERITY = 60
SEVERITIES = ["mild", "moderate", "severe", "critical"]
OUTPUT_PATH = Path(BACKEND_DIR) / "tests" / "fixtures" / "golden_feature_vectors.json"

# Arbitrary fixed instant — kept only as the defensive datetime.now() fallback
# described above; every generated patient's _reference_month takes priority
# over it. Must match FROZEN_REFERENCE_TIME in test_feature_parity.py.
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
