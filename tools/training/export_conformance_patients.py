"""
One-time (+ re-runnable) conformance export for the TypeScript migration
(DECISIONS.md §33 / the Round 6 rebuild plan, Phase 1): generates N
synthetic patients, runs the CURRENT PRODUCTION Python inference path
(app.ml.classifier.predict_triage — safety net -> trained model -> NEWS2
floor) on every one, and writes the patient + Python's verdict to
packages/clinical-core/test/conformance/patients_with_python_tier.jsonl.

packages/clinical-core/test/conformance/hybrid.conformance.test.ts then
replays the same patients through clinical-core's triage() in "hybrid"
mode (the mode that reproduces this exact safety-net -> model -> floor
order) and asserts the tiers agree — proof the TypeScript port changed
nothing before rules_first ever ships. It is NOT a golden-vector fixture:
patients are freshly generated (seeded) each run, so re-running this
script after a genuine model retrain also re-validates the port against
the new model, not a frozen snapshot.

_reference_month is set on every patient (as in export_golden_vectors.py)
so seasonal_risk is reproducible read on both sides; FROZEN_REFERENCE_TIME
is the defensive datetime.now() fallback, matching that script.

Run: cd tools/training && python export_conformance_patients.py [N]
(default N=10000)
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

from app.ml.classifier import load_classifier, predict_triage  # noqa: E402
from train_classifier import generate_patient  # noqa: E402

OUTPUT_PATH = (
    Path(__file__).parent.parent.parent
    / "packages" / "clinical-core" / "test" / "conformance" / "patients_with_python_tier.jsonl"
)

FROZEN_REFERENCE_TIME = _real_datetime(2026, 7, 4, 12, 0, 0)


class _FrozenDateTime(_real_datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_REFERENCE_TIME.replace(tzinfo=tz)


# Same severity mix as build_dataset()'s generation weights (train_classifier.py)
# so the conformance set's case mix resembles what the model was trained on,
# not an artificially uniform one.
SEVERITIES = ["healthy", "mild", "moderate", "severe", "critical"]
SEVERITY_WEIGHTS = [0.30, 0.22, 0.22, 0.16, 0.10]
PEDIATRIC_FRACTION = 0.22


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    seed = 20260711
    np.random.seed(seed)

    print(f"Loading classifier...")
    load_classifier()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating {n} synthetic patients and running predict_triage on each...")
    tier_counts = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
    with patch("app.ml.clinical_features.datetime", _FrozenDateTime), open(OUTPUT_PATH, "w") as f:
        for i in range(n):
            severity = np.random.choice(SEVERITIES, p=SEVERITY_WEIGHTS)
            pediatric = np.random.random() < PEDIATRIC_FRACTION
            patient = generate_patient(severity, pediatric=pediatric)

            result = predict_triage(patient)
            tier_counts[result["triage_level"]] += 1

            record = dict(patient)
            record["python_tier"] = result["triage_level"]
            record["python_confidence"] = result["confidence_score"]
            record["python_safety_net_triggered"] = result["safety_net_triggered"]
            f.write(json.dumps(record) + "\n")

            if (i + 1) % 2000 == 0:
                print(f"  ...{i + 1}/{n}")

    print(f"Wrote {n} records to {OUTPUT_PATH}")
    print(f"Tier distribution: {tier_counts}")


if __name__ == "__main__":
    main()
