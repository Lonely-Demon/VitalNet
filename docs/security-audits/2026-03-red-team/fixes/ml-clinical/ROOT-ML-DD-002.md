# Fix Log: ROOT-ML-DD-002

## Issue Solved
Unknown ONNX label indices no longer silently collapse into ROUTINE.

## Fix Applied
Updated `frontend/src/utils/triageClassifier.js` to return a review-required emergency path when the ONNX label index is unknown.

## Files Changed
- frontend/src/utils/triageClassifier.js

## Verification
- Frontend build passed after removing the silent ROUTINE fallback
