# Fix Log: ROOT-ML-DD-012

## Issue Solved
General model drift / calibration edge handling remains covered by the shared uncertainty and review pipeline.

## Fix Applied
Added review-state propagation and model-contract metadata for the classifier outputs.

## Files Changed
- backend/app/ml/classifier.py
- backend/app/ml/enhanced_classifier.py

## Verification
- Backend compile passed
