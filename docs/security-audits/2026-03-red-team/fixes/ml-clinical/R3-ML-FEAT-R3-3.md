# Fix Log: R3-ML-FEAT-R3-3

## Issue Solved
Blank and non-finite numeric inputs are now handled explicitly.

## Fix Applied
Added numeric coercion helpers and missing-vital penalties in the feature engineer.

## Files Changed
- backend/app/ml/clinical_features.py

## Verification
- Backend compile passed
