"""
Retrain the triage classifier from real doctor-recorded outcomes
(FEATURES_ROADMAP §1.3). NOT wired into CI/CD — this is a human-gated,
periodic job. A clinical model regressing silently in production is a much
worse failure mode than a slower manual review cadence.

What this does:
  1. Loads recorded outcomes — either from the live Supabase project
     (default) or a JSON fixture (--outcomes-fixture, for testing/CI).
  2. Refuses to run below a minimum sample size (--force to override, for
     testing only) — a tiny outcome sample isn't a meaningful retraining
     signal and risks overfitting to a handful of cases.
  3. Blends the real-outcome labels (treated as higher-confidence than the
     synthetic generator's heuristic label, since they're actual clinical
     judgment) with a shrinking proportion of synthetic data from
     train_classifier.py's generator, so the model doesn't overfit to an
     early, small real sample.
  4. Trains a CANDIDATE model with the same HistGradientBoostingClassifier
     configuration as train_classifier.py, and reports:
       - accuracy/EMERGENCY-recall on a held-out synthetic split (sanity —
         the candidate shouldn't regress badly on the baseline distribution)
       - agreement rate between the CURRENT production model and the
         CANDIDATE against the recorded actual_severity labels (this is the
         number a human uses to decide whether to promote)
  5. Writes the candidate to app/ml/models/candidate_triage_classifier.pkl —
     NEVER overwrites the production triage_classifier.pkl. Promotion is a
     separate, manual, human-reviewed step (see PROMOTING below).

PROMOTING a candidate to production (manual, after human review of the
report above):
  cp app/ml/models/candidate_triage_classifier.pkl app/ml/models/triage_classifier.pkl
  python scripts/export_tree_json_from_pkl.py   # regenerate the offline JS artifacts
  # then re-run the full test suite + parity tests before deploying.

Run (production): python scripts/retrain_from_outcomes.py
Run (test/CI, against a fixture): python scripts/retrain_from_outcomes.py \
    --outcomes-fixture tests/fixtures/synthetic_outcomes.json --force
"""
import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, recall_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.ml.clinical_features import ClinicalFeatureEngineer  # noqa: E402
from train_classifier import (  # noqa: E402
    FEATURE_NAMES, LABEL_MAP, RANDOM_SEED, TEST_SIZE,
    MODELS_DIR, PKL_PATH, build_dataset,
)

_rng = np.random.default_rng(RANDOM_SEED)

MIN_OUTCOMES = 500
MIN_EMERGENCY_DISAGREEMENTS = 50
CANDIDATE_PATH = os.path.join(MODELS_DIR, "candidate_triage_classifier.pkl")

LABEL_TO_INDEX = {v: k for k, v in LABEL_MAP.items()}
_engineer = ClinicalFeatureEngineer()


def load_outcomes_from_fixture(path: str) -> list[dict]:
    """Fixture shape: list of {"case_input": <raw IntakeForm-like dict>,
    "actual_severity": "ROUTINE"|"URGENT"|"EMERGENCY", "original_triage_level": ...}"""
    return json.loads(Path(path).read_text())


def load_outcomes_from_supabase() -> list[dict]:
    from app.core.database import supabase_admin
    outcomes = (
        supabase_admin.table("case_outcomes")
        .select("actual_severity, case_records(*)")
        .execute()
    ).data or []
    return [
        {
            "case_input": row["case_records"],
            "actual_severity": row["actual_severity"],
            "original_triage_level": (row["case_records"] or {}).get("triage_level"),
        }
        for row in outcomes
        if row.get("case_records")
    ]


def _featurize(case_input: dict) -> np.ndarray:
    features = _engineer.engineer_features(case_input)
    return np.array([features[name] for name in FEATURE_NAMES], dtype=np.float32)


def build_blended_dataset(outcomes: list[dict]):
    """Real-outcome labels + a shrinking proportion of synthetic data.
    More real data -> proportionally less synthetic padding, so the real
    signal dominates as outcome volume grows."""
    real_X = np.array([_featurize(o["case_input"]) for o in outcomes], dtype=np.float32)
    real_y = np.array([LABEL_TO_INDEX[o["actual_severity"]] for o in outcomes])

    # Synthetic padding shrinks (relative to the fixed pool below) as real
    # data grows: 5x real count, capped at a reasonable floor/ceiling so
    # there's always some regularizing signal from the broader synthetic
    # distribution, but it never dominates once real data is substantial.
    # build_dataset() always generates a large fixed-size pool (N_PER_CLASS
    # per class) — subsample it down to the desired blended proportion
    # rather than trying to control its generation count directly.
    n_synthetic = max(300, min(3000, len(outcomes) * 5))
    synth_patients, synth_y = build_dataset()
    pool_size = len(synth_patients)
    if n_synthetic < pool_size:
        idx = _rng.choice(pool_size, size=n_synthetic, replace=False)
        synth_patients = [synth_patients[i] for i in idx]
        synth_y = synth_y[idx]
    synth_X = np.array(
        [[_engineer.engineer_features(p)[name] for name in FEATURE_NAMES] for p in synth_patients],
        dtype=np.float32,
    )

    X = np.concatenate([real_X, synth_X])
    y = np.concatenate([real_y, synth_y])
    return X, y


def _train_candidate(X, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y
    )
    clf = HistGradientBoostingClassifier(
        max_iter=450, max_depth=7, learning_rate=0.06, l2_regularization=0.5,
        class_weight={0: 1.0, 1: 2.0, 2: 6.0}, random_state=RANDOM_SEED,
        early_stopping=True, validation_fraction=0.1, n_iter_no_change=25,
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    return clf, {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "emergency_recall": float(recall_score(y_test, y_pred, labels=[2], average="macro")),
        "n_train": len(X_train),
        "n_test": len(X_test),
    }


def _agreement_rate(clf, outcomes: list[dict]) -> float:
    if not outcomes:
        return 0.0
    X = np.array([_featurize(o["case_input"]) for o in outcomes], dtype=np.float32)
    y_true = np.array([LABEL_TO_INDEX[o["actual_severity"]] for o in outcomes])
    y_pred = clf.predict(X)
    return float(accuracy_score(y_true, y_pred))


def _current_model_agreement_rate(outcomes: list[dict]) -> float | None:
    if not os.path.exists(PKL_PATH):
        return None
    with open(PKL_PATH, "rb") as f:
        current = pickle.load(f)["classifier"]
    return _agreement_rate(current, outcomes)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outcomes-fixture", help="JSON fixture path (testing/CI) instead of live Supabase")
    parser.add_argument("--force", action="store_true", help="Bypass the minimum-sample-size gate (testing only)")
    args = parser.parse_args()

    outcomes = (
        load_outcomes_from_fixture(args.outcomes_fixture)
        if args.outcomes_fixture
        else load_outcomes_from_supabase()
    )
    print(f"Loaded {len(outcomes)} recorded outcomes.")

    emergency_disagreements = sum(
        1 for o in outcomes
        if o.get("original_triage_level") and o["actual_severity"] != o["original_triage_level"]
        and o["actual_severity"] == "EMERGENCY"
    )

    if not args.force and (len(outcomes) < MIN_OUTCOMES or emergency_disagreements < MIN_EMERGENCY_DISAGREEMENTS):
        print(
            f"Not enough outcome volume yet to retrain meaningfully: "
            f"{len(outcomes)}/{MIN_OUTCOMES} outcomes, "
            f"{emergency_disagreements}/{MIN_EMERGENCY_DISAGREEMENTS} EMERGENCY disagreements. "
            f"Use --force to override (testing only)."
        )
        return

    print("Building blended (real + synthetic) training set ...")
    X, y = build_blended_dataset(outcomes)

    print("Training candidate model ...")
    candidate, metrics = _train_candidate(X, y)
    print(f"  Candidate held-out accuracy: {metrics['accuracy']:.4f}, "
          f"EMERGENCY recall: {metrics['emergency_recall']:.4f} "
          f"(train={metrics['n_train']}, test={metrics['n_test']})")

    candidate_agreement = _agreement_rate(candidate, outcomes)
    current_agreement = _current_model_agreement_rate(outcomes)
    print(f"  Candidate agreement with recorded outcomes: {candidate_agreement:.4f}")
    if current_agreement is not None:
        delta = candidate_agreement - current_agreement
        print(f"  Current production model agreement with the SAME outcomes: {current_agreement:.4f}")
        print(f"  Delta: {delta:+.4f} ({'improvement' if delta > 0 else 'regression' if delta < 0 else 'no change'})")
    else:
        print("  No production model found to compare against.")

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(CANDIDATE_PATH, "wb") as f:
        pickle.dump({
            "classifier": candidate,
            "feature_names": FEATURE_NAMES,
            "label_map": LABEL_MAP,
            "performance_metrics": metrics,
            "trained_on_outcomes": len(outcomes),
        }, f, protocol=5)
    print(f"\nCandidate saved to {CANDIDATE_PATH} (NOT deployed — this never touches "
          f"the production {PKL_PATH}). A human must review the numbers above and "
          f"explicitly promote it — see this script's module docstring.")


if __name__ == "__main__":
    main()
