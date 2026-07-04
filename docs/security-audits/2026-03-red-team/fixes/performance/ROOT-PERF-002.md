# VitalNet Performance Fix: ONNX Runtime Loading Optimization

## Issue Solved
The ONNX runtime library (~2MB) was being loaded for ALL users on app startup, even for non-ASHA workers who never use the ASHA triage feature, resulting in unnecessary bandwidth usage.

## Fix Applied
Converted static import of ONNX runtime to dynamic import pattern so the library is only loaded when `loadModel()` or `runTriage()` is first called, implementing lazy loading to prevent loading the ~2MB ONNX WebAssembly bundle for non-ASHA users.

## Why This Fix Was Chosen
This fix was chosen to address performance issues with the large 2MB ONNX library that was previously loaded for all users regardless of their need for the ASHA triage feature. The fix implements lazy loading to ensure the library is only loaded when actually needed, improving performance for non-ASHA users.

## Files Changed
- `frontend/src/utils/triageClassifier.js`

## Verification
The fix implements code splitting to ensure the ONNX runtime is only loaded when accessed by ASHA workers, reducing the initial load for all users.