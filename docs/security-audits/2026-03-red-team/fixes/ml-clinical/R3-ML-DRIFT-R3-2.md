# Fix Log: R3-ML-DRIFT-R3-2

## Issue Solved
Drift metrics are no longer training-only; live prediction telemetry is recorded.

## Fix Applied
Added lightweight live drift counters and averages to the enhanced classifier.

## Files Changed
- backend/app/ml/enhanced_classifier.py

## Verification
- Backend compile passed
