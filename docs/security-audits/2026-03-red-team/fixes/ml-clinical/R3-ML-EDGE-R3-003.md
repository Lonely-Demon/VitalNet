# Fix Log: R3-ML-EDGE-R3-003

## Issue Solved
Symptoms are normalized before scoring.

## Fix Applied
Added symptom canonicalization in both backend and frontend feature engineering paths.

## Files Changed
- backend/app/ml/clinical_features.py
- frontend/src/utils/triageClassifier.js

## Verification
- Backend compile passed
- Frontend build passed
