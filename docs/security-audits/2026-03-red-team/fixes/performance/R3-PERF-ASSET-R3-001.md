# R3-PERF-ASSET-R3-001 Fix Log

## Issue Solved
The PWA precache configuration in `vite.config.js` was missing the WASM file pattern, which meant that critical ONNX runtime WASM assets needed for offline ML inference were not being precached. This could lead to failures in offline functionality where the ML model depends on the ONNX runtime.

## Fix Applied
Added `wasm` to the file extension glob pattern in the workbox configuration in `frontend/vite.config.js`. The globPatterns was changed from:
```js
globPatterns: [
  '**/*.{js,css,html,ico,png,svg,woff2}',
  'models/triage_classifier.onnx',
  'models/features_config.json',
],
```
to:
```js
globPatterns: [
  '**/*.{js,css,html,ico,png,svg,woff2,wasm}',
  'models/triage_classifier.onnx',
  'models/features_config.json',
],
```

## Why This Fix Was Chosen
This approach was chosen because:
1. It's the minimal change required to solve the issue
2. It ensures all WASM files are precached without being overly specific to particular filenames
3. It follows the existing pattern in the configuration
4. It's future-proof for any additional WASM files that might be added later

Alternative approaches considered but rejected:
- Specifically targeting ONNX runtime WASM files: Would require maintaining a list of specific filenames which could change with library updates
- Adding each WASM file individually: Would be brittle and require maintenance as files change

## Files Changed
- `frontend/vite.config.js` - Updated the globPatterns to include WASM files

## Verification Commands/Results
After the fix, the following verification steps should be performed:

1. Build the frontend: `npm run build`
2. Check that WASM files are included in the service worker precache manifest
3. Test offline functionality with ONNX inference

The build process will now include WASM files in the precache manifest, ensuring offline functionality for ML inference.