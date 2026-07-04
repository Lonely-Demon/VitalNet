# Fix Log: ROOT-ML-DD-007

## Issue Solved
High-risk clinical red flags are now explicitly detected and escalated.

## Fix Applied
Added stroke / anaphylaxis / acute-abdomen red-flag rules to the clinical feature engineer and triage inference path.

## Files Changed
- backend/app/ml/clinical_features.py
- backend/app/ml/enhanced_classifier.py
- frontend/src/utils/triageClassifier.js

## Verification
- Backend compile passed
- Frontend build passed
