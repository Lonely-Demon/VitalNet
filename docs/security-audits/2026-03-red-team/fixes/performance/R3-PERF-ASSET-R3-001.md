# Fix Log: R3-PERF-ASSET-R3-001

## Issue Solved
Heavy ML assets (`.wasm`, `.onnx`) did not have an explicit runtime caching policy with expiry. This caused avoidable re-downloads and inconsistent offline behavior for model execution.

## Fix Applied
Updated `frontend/vite.config.js` Workbox config to:

1. Keep app-shell precache focused on core static assets.
2. Add **runtime CacheFirst** for ML assets:
   - `url.pathname.endsWith('.wasm')`
   - `url.pathname.endsWith('.onnx')`
   - `url.pathname.includes('/models/')`
3. Add cache policy:
   - `cacheName: 'ml-assets-cache'`
   - `maxEntries: 12`
   - `maxAgeSeconds: 7 * 24 * 60 * 60` (7 days)
   - `cacheableResponse.statuses: [0, 200]`

## Why This Fix Was Chosen
- `CacheFirst` is appropriate for large, versioned model/runtime artifacts.
- Expiration bounds storage growth while preserving offline resilience.
- Runtime caching avoids bloating critical app-shell precache.

## Files Changed
- `frontend/vite.config.js`

## Verification
- `npm run build` succeeds.
- Build output still emits ONNX/WASM assets and service worker generation.
- Runtime caching configuration now explicitly includes WASM/ONNX/model paths with expiry.
