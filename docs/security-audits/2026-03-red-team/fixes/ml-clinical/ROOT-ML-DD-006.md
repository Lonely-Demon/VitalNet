# Fix Log: ROOT-ML-DD-006

## Issue Solved
Frontend/backend model-version mismatches are now detectable.

## Fix Applied
Added model contract versioning and artifact hashing, and surfaced schema/version metadata through the classifier path.

## Files Changed
- backend/app/ml/model_contract.py
- frontend/src/utils/modelContract.js
- backend/app/ml/classifier.py
- backend/app/ml/enhanced_classifier.py
- frontend/src/utils/triageClassifier.js

## Verification
- Backend compile passed
- Frontend build passed
