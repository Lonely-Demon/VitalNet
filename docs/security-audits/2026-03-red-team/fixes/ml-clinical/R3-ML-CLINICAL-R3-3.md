# Fix Log: R3-ML-CLINICAL-R3-3

## Issue Solved
Impossible blood-pressure combinations are blocked at validation time.

## Fix Applied
Added a Pydantic post-validation rule ensuring diastolic BP remains below systolic BP.

## Files Changed
- backend/app/models/schemas.py

## Verification
- Backend compile passed
