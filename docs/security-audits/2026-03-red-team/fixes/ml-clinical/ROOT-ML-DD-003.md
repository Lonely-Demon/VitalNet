# Fix Log: ROOT-ML-DD-003

## Issue Solved
Low-confidence / uncertain triage predictions now surface review state instead of presenting a normal-confidence flow.

## Fix Applied
Added confidence-floor and uncertainty gating in backend and frontend model contract handling.

## Files Changed
- backend/app/ml/enhanced_classifier.py
- backend/app/ml/classifier.py
- frontend/src/utils/triageClassifier.js

## Verification
- Backend compile passed
- Frontend build passed
