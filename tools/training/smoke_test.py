#!/usr/bin/env python3
"""
Fast CI smoke test for the clinical-core cli.mjs subprocess wiring — NOT a
full training run (that takes too long for a PR check and would overwrite
the committed model artifacts with a degenerate model). Exercises exactly
the part train_classifier.py's Round 6 refactor changed: patient generation
-> assign_triage_labels() -> engineer_features_batch(), all the way through
build_dataset() with a small n_per_class, at the SAME CLI_BATCH_SIZE
sub-batching path production training uses (just fewer batches).

Requires `pnpm --filter @vitalnet/clinical-core build` to have already run
(same precondition as train_classifier.py itself).

Run: cd tools/training && python smoke_test.py
"""
import sys

import numpy as np

import train_classifier as tc

SMOKE_N_PER_CLASS = 40


def main():
    np.random.seed(1)

    print(f"Deriving FEATURE_NAMES via cli.mjs ... {tc.NUM_FEATURES} features")
    assert tc.NUM_FEATURES > 0, "FEATURE_NAMES came back empty"

    print("Generating a small labeled patient set through cli.mjs 'label' ...")
    patients, y = tc.build_dataset(n_per_class=SMOKE_N_PER_CLASS)
    assert len(patients) == 3 * SMOKE_N_PER_CLASS, f"expected {3 * SMOKE_N_PER_CLASS} patients, got {len(patients)}"
    for c in (0, 1, 2):
        count = int((y == c).sum())
        assert count == SMOKE_N_PER_CLASS, f"class {c}: expected {SMOKE_N_PER_CLASS}, got {count}"

    print("Engineering features through cli.mjs 'engineer-features' ...")
    feature_maps = tc.engineer_features_batch(patients)
    assert len(feature_maps) == len(patients)
    for fm in feature_maps[:5]:
        assert set(fm.keys()) == set(tc.FEATURE_NAMES), "feature map keys don't match FEATURE_NAMES"
        assert all(isinstance(v, (int, float)) for v in fm.values()), "non-numeric feature value"

    print(f"OK — {len(patients)} patients labeled and featurized via clinical-core cli.mjs.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"SMOKE TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)
