"""Trusted-artifact checks for human-gated candidate retraining."""

from pathlib import Path

import pytest

from retrain_from_outcomes import (
    FROZEN_PRODUCTION_MODEL_SHA256,
    PKL_PATH,
    _sha256_file,
    verify_frozen_production_model,
)


def test_frozen_production_model_matches_recorded_hash():
    assert _sha256_file(PKL_PATH) == FROZEN_PRODUCTION_MODEL_SHA256
    verify_frozen_production_model()


def test_tampered_model_is_rejected(tmp_path: Path):
    tampered = tmp_path / "triage_classifier.pkl"
    tampered.write_bytes(b"synthetic-tampered-artifact")

    with pytest.raises(RuntimeError, match="hash mismatch"):
        verify_frozen_production_model(str(tampered))
