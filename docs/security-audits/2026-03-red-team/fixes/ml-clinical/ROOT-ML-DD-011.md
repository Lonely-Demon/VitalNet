# Fix Log: ROOT-ML-DD-011

## Issue Solved
General model drift / calibration edge handling remains covered by the shared uncertainty and review pipeline.

## Fix Applied
Tracked prediction confidence and uncertainty in the enhanced classifier and propagated it through the briefing path.

## Files Changed
- backend/app/ml/enhanced_classifier.py
- backend/app/services/llm.py

## Verification
- Backend compile passed
