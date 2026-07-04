# Fix Log: ROOT-ML-DD-005

## Issue Solved
Invalid or missing input ranges now stay explicit instead of being coerced into normal-looking values.

## Fix Applied
Added numeric coercion guards and missing-vital penalties in the feature engineer and validation constraints in the intake schema.

## Files Changed
- backend/app/ml/clinical_features.py
- backend/app/models/schemas.py

## Verification
- Backend compile passed
