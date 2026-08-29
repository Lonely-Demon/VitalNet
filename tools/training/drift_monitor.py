#!/usr/bin/env python3
"""
ML feature-drift monitor — compares the live case_records feature
distribution against a synthetic reference distribution built from the
same generator train_classifier.py trains on, using the Population
Stability Index (PSI) per engineered feature.

This is an operator-run diagnostic against a real Supabase project (needs
SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY configured, same as any other
backend script) — it takes no automatic action and is not wired to a
schedule. Re-run it periodically, or whenever triage behaviour looks off,
to check whether the population VitalNet is actually seeing has drifted
away from what the model was trained on (case mix, vitals distribution,
missing-vitals rate, etc.) — see docs/CLINICAL_GOVERNANCE.md's model
lifecycle governance section.

PSI interpretation (standard convention):
    < 0.10           no significant shift
    0.10 - 0.25      moderate shift — worth a look
    > 0.25           significant shift — investigate before trusting
                     current metrics against this population

Usage:
    cd backend && source venv/bin/activate
    PYTHONPATH=. python scripts/drift_monitor.py [--reference-n 4000] [--live-n 500] [--since-days 90]
"""
import argparse
import os
import sys

import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.dirname(__file__))

from train_classifier import generate_patient  # noqa: E402
from app.ml.clinical_features import ClinicalFeatureEngineer  # noqa: E402

REFERENCE_SEED = 42  # matches train_classifier.py's RANDOM_SEED — same generating distribution
SEVERITIES = ["healthy", "mild", "moderate", "severe", "critical"]
SEVERITY_WEIGHTS = [0.30, 0.22, 0.22, 0.16, 0.10]

MIN_LIVE_SAMPLES = 50
PSI_MODERATE = 0.10
PSI_SIGNIFICANT = 0.25

_engineer = ClinicalFeatureEngineer()

CASE_RECORD_COLUMNS = (
    "patient_age, patient_sex, patient_location, bp_systolic, bp_diastolic, "
    "spo2, heart_rate, temperature, symptoms, chief_complaint, "
    "complaint_duration, known_conditions, created_at"
)


def _case_row_to_form_data(row: dict) -> dict:
    """case_records' column names don't all match what engineer_features()
    reads (notably patient_location vs. the `location` key it expects) —
    remap here rather than in the feature engineer itself, which mirrors
    the frontend's field names on purpose (docs/DECISIONS.md §2)."""
    return {**row, "location": row.get("patient_location", "")}


def population_stability_index(reference: np.ndarray, live: np.ndarray, buckets: int = 10) -> float:
    quantile_edges = np.quantile(reference, np.linspace(0, 1, buckets + 1))
    edges = np.unique(quantile_edges)
    if len(edges) < 3:
        return 0.0  # near-constant feature in the reference set — nothing meaningful to compare

    ref_counts, _ = np.histogram(reference, bins=edges)
    live_counts, _ = np.histogram(live, bins=edges)
    ref_pct = np.clip(ref_counts / max(len(reference), 1), 1e-4, None)
    live_pct = np.clip(live_counts / max(len(live), 1), 1e-4, None)
    return float(np.sum((live_pct - ref_pct) * np.log(live_pct / ref_pct)))


def build_reference_features(n: int) -> dict[str, np.ndarray]:
    print(f"Generating {n} synthetic reference patients (seed={REFERENCE_SEED}) ...")
    np.random.seed(REFERENCE_SEED)
    rows = []
    for _ in range(n):
        severity = np.random.choice(SEVERITIES, p=SEVERITY_WEIGHTS)
        patient = generate_patient(severity)
        rows.append(_engineer.engineer_features(patient))
    return _to_columns(rows)


def fetch_live_features(n: int, since_days: int) -> dict[str, np.ndarray]:
    from datetime import datetime, timedelta, timezone
    from app.core.database import supabase_admin

    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    print(f"Fetching up to {n} live case_records since {since[:10]} ...")
    result = (
        supabase_admin.table("case_records")
        .select(CASE_RECORD_COLUMNS)
        .is_("deleted_at", "null")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(n)
        .execute()
    )
    live_rows = result.data or []
    print(f"       Found {len(live_rows)} live case(s) in the window.")
    if len(live_rows) < MIN_LIVE_SAMPLES:
        return {}

    rows = [_engineer.engineer_features(_case_row_to_form_data(row)) for row in live_rows]
    return _to_columns(rows)


def _to_columns(rows: list[dict[str, float]]) -> dict[str, np.ndarray]:
    if not rows:
        return {}
    keys = rows[0].keys()
    return {k: np.array([r[k] for r in rows], dtype=np.float64) for k in keys}


def run_drift_check(reference_n: int, live_n: int, since_days: int):
    reference = build_reference_features(reference_n)
    live = fetch_live_features(live_n, since_days)

    if not live:
        print(f"\nFewer than {MIN_LIVE_SAMPLES} live cases in the last {since_days} day(s) — "
              "not enough data for a meaningful drift check yet. Try a wider --since-days.")
        return

    shared_features = sorted(set(reference) & set(live))
    results = []
    for feature in shared_features:
        psi = population_stability_index(reference[feature], live[feature])
        results.append((feature, psi))
    results.sort(key=lambda x: x[1], reverse=True)

    print(f"\n=== Feature drift (PSI), {len(results)} feature(s), sorted by drift ===")
    significant = []
    moderate = []
    for feature, psi in results:
        if psi > PSI_SIGNIFICANT:
            tag = "  <-- SIGNIFICANT"
            significant.append(feature)
        elif psi > PSI_MODERATE:
            tag = "  <-- moderate"
            moderate.append(feature)
        else:
            tag = ""
        print(f"  {feature:32s} PSI={psi:.4f}{tag}")

    print("\n=== Summary ===")
    if significant:
        print(f"{len(significant)} feature(s) show SIGNIFICANT drift (PSI > {PSI_SIGNIFICANT}): "
              f"{', '.join(significant)}")
        print("Investigate before trusting current model metrics against this live population — "
              "consider scripts/retrain_from_outcomes.py once enough real outcomes exist.")
    elif moderate:
        print(f"{len(moderate)} feature(s) show moderate drift (PSI > {PSI_MODERATE}): "
              f"{', '.join(moderate)}. Worth a look, not yet urgent.")
    else:
        print("No feature exceeded the moderate drift threshold.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reference-n", type=int, default=4000, help="Synthetic reference sample size")
    parser.add_argument("--live-n", type=int, default=500, help="Max live case_records rows to sample")
    parser.add_argument("--since-days", type=int, default=90, help="Only consider live cases created within this many days")
    args = parser.parse_args()
    run_drift_check(args.reference_n, args.live_n, args.since_days)
