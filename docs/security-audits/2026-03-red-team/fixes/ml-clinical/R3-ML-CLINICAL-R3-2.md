# Fix Log: R3-ML-CLINICAL-R3-2

## Issue Solved
Missing vitals are no longer treated as normal.

## Fix Applied
Added missing-vital penalties and explicit fallback handling in the clinical feature engineer.

## Files Changed
- backend/app/ml/clinical_features.py

## Verification
- Backend compile passed
