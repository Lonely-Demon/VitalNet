# Fix Log: R3-ML-FEAT-R3-1

## Issue Solved
Age zero is no longer silently rewritten to an adult-default signal.

## Fix Applied
Normalized the backend feature pipeline to preserve explicit missing/unknown age handling and penalize unknowns rather than normalizing to healthy adults.

## Files Changed
- backend/app/ml/clinical_features.py

## Verification
- Backend compile passed
