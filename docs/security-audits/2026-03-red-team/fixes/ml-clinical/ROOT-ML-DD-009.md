# Fix Log: ROOT-ML-DD-009

## Issue Solved
Confidence / calibration issues now produce review signals and live drift telemetry.

## Fix Applied
Added uncertainty gating, live drift metrics, and review-required flags in the enhanced classifier and client inference path.

## Files Changed
- backend/app/ml/enhanced_classifier.py
- frontend/src/utils/triageClassifier.js

## Verification
- Backend compile passed
- Frontend build passed
