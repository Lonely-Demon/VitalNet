# Fix Log: ROOT-ML-DD-004

## Issue Solved
Frontend/backend feature schema drift is reduced by sharing normalization and model-contract constants.

## Fix Applied
Added shared model contract files and normalized symptoms / vitals consistently across backend and frontend.

## Files Changed
- backend/app/ml/model_contract.py
- frontend/src/utils/modelContract.js
- backend/app/ml/clinical_features.py
- frontend/src/utils/triageClassifier.js

## Verification
- Backend compile passed
- Frontend build passed
