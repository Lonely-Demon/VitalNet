# Fix Log: ROOT-PERF-002

## Issue Solved
The ONNX runtime library (~2MB) was being loaded for ALL users, even non-ASHA workers, causing unnecessary bundle size and performance impact.

## Fix Applied
Converted the static import of ONNX runtime to dynamic import, so it's only loaded when needed for actual inference.

## Why This Fix Was Chosen
This approach uses code splitting to defer loading of the large ONNX runtime library until it's actually needed, reducing initial bundle size and improving app startup time for all users.

## Files Changed
- frontend/src/utils/triageClassifier.js

## Verification
- Confirmed that ONNX runtime is no longer loaded on app startup
- Only loaded when runTriage() is first called
- Reduced initial bundle loading for non-ASHA workers