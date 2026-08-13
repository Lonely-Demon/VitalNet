#!/usr/bin/env python3
"""
ML fairness audit — subgroup performance analysis (age band × sex).

Generates a fresh synthetic evaluation population (same generator as
train_classifier.py, a different random seed so it isn't literally the
training data), runs every patient through the FULL deployed triage
pipeline (app.ml.classifier.predict_triage — safety net + trained model +
NEWS2 floor, not just the raw classifier), and reports accuracy and
EMERGENCY recall broken down by age band and sex. Any subgroup whose
EMERGENCY recall or accuracy falls notably below the population average is
flagged for human review.

This is a synthetic-data audit, not a real-world bias audit — VitalNet has
no real patient data to check subgroup fairness against (see
MODEL_CARD.md's training-data caveat and docs/CLINICAL_GOVERNANCE.md). It
tells you whether the model's behaviour on the *synthetic label
generator's* notion of these patients is consistent across age/sex, which
is a narrower but still useful check: a large gap here would mean the
model learned some age/sex-correlated shortcut instead of the clinical
signal, which would be worth understanding before trusting the model on
any subgroup. It takes no automatic action — an operator reads the report.

Usage:
    cd backend && source venv/bin/activate
    PYTHONPATH=. python scripts/fairness_audit.py [--n 6000] [--flag-gap 0.10]
"""
import argparse
import os
import sys

import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.dirname(__file__))

from train_classifier import generate_patient, assign_triage_labels, LABEL_MAP  # noqa: E402
from app.ml.classifier import load_classifier, predict_triage  # noqa: E402

SEED = 20260704  # deliberately different from train_classifier.py's RANDOM_SEED
SEVERITIES = ["healthy", "mild", "moderate", "severe", "critical"]
SEVERITY_WEIGHTS = [0.30, 0.22, 0.22, 0.16, 0.10]

AGE_BANDS = [
    ("infant (<2)", 0, 2),
    ("child (2-11)", 2, 12),
    ("adolescent (12-17)", 12, 18),
    ("adult (18-64)", 18, 65),
    ("elderly (65+)", 65, 200),
]
MIN_SUBGROUP_SIZE = 30  # below this, flag "insufficient data" rather than report a number


def age_band(age: float) -> str:
    for label, lo, hi in AGE_BANDS:
        if lo <= age < hi:
            return label
    return "unknown"


def run_audit(n_total: int, flag_gap: float):
    print("Loading triage classifier bundle ...")
    load_classifier()

    np.random.seed(SEED)  # generate_patient uses the global np.random state

    print(f"Generating {n_total} synthetic evaluation patients ...")
    patients = [generate_patient(np.random.choice(SEVERITIES, p=SEVERITY_WEIGHTS)) for _ in range(n_total)]

    print("Labeling via clinical-core cli.mjs ...")
    labels = assign_triage_labels(patients)

    print("Running the full deployed triage pipeline on each patient ...")
    rows = []
    for patient, label in zip(patients, labels):
        predicted = predict_triage(patient)["triage_level"]
        rows.append({
            "age_band": age_band(patient["patient_age"]),
            "sex": patient["patient_sex"],
            "true": LABEL_MAP[label],
            "predicted": predicted,
        })

    _report(rows, flag_gap)


def _metrics(rows: list[dict]) -> dict:
    n = len(rows)
    correct = sum(1 for r in rows if r["true"] == r["predicted"])
    emergency_true = [r for r in rows if r["true"] == "EMERGENCY"]
    emergency_recall = (
        sum(1 for r in emergency_true if r["predicted"] == "EMERGENCY") / len(emergency_true)
        if emergency_true else None
    )
    return {
        "n": n,
        "accuracy": correct / n if n else None,
        "emergency_recall": emergency_recall,
        "n_emergency": len(emergency_true),
    }


def _report(rows: list[dict], flag_gap: float):
    overall = _metrics(rows)
    print("\n=== Overall ===")
    print(f"n={overall['n']}  accuracy={overall['accuracy']:.4f}  "
          f"EMERGENCY recall={overall['emergency_recall']:.4f} (n_emergency={overall['n_emergency']})")

    flags = []

    def _check_subgroups(key: str, label: str):
        print(f"\n=== By {label} ===")
        groups = sorted({r[key] for r in rows})
        for g in groups:
            sub = [r for r in rows if r[key] == g]
            m = _metrics(sub)
            if m["n"] < MIN_SUBGROUP_SIZE:
                print(f"  {g:22s} n={m['n']:5d}  (insufficient data — skipped)")
                continue
            acc_gap = overall["accuracy"] - m["accuracy"]
            recall_gap = (
                overall["emergency_recall"] - m["emergency_recall"]
                if m["emergency_recall"] is not None and overall["emergency_recall"] is not None
                else None
            )
            flagged = acc_gap > flag_gap or (recall_gap is not None and recall_gap > flag_gap)
            marker = "  <-- FLAGGED" if flagged else ""
            recall_str = f"{m['emergency_recall']:.4f}" if m["emergency_recall"] is not None else "n/a"
            print(f"  {g:22s} n={m['n']:5d}  accuracy={m['accuracy']:.4f}  "
                  f"EMERGENCY recall={recall_str} (n_emergency={m['n_emergency']}){marker}")
            if flagged:
                flags.append((label, g, m))

    _check_subgroups("age_band", "age band")
    _check_subgroups("sex", "sex")

    print("\n=== Summary ===")
    if flags:
        print(f"{len(flags)} subgroup(s) flagged (>{flag_gap:.0%} below population average on "
              f"accuracy or EMERGENCY recall):")
        for label, g, m in flags:
            print(f"  - {label}: {g} (n={m['n']})")
        print("\nThis flags a gap for human review — it is not proof of unfair or "
              "unsafe behaviour on real patients (this is synthetic-data evaluation, "
              "see the module docstring and MODEL_CARD.md). Investigate before "
              "concluding anything about real-world subgroup performance.")
    else:
        print(f"No subgroup exceeded the {flag_gap:.0%} gap threshold against the "
              "population average on this synthetic evaluation set.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=6000, help="Total synthetic patients to evaluate")
    parser.add_argument("--flag-gap", type=float, default=0.10,
                         help="Flag a subgroup if its accuracy or EMERGENCY recall falls this much "
                              "(as a fraction, e.g. 0.10 = 10 percentage points) below the population average")
    args = parser.parse_args()
    run_audit(args.n, args.flag_gap)
