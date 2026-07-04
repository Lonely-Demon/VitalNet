# Fix Log: R3-PERF-NET-R3-06

## Issue Solved
The connectivity probe endpoint could diverge from the configured API base, which risks false reachability results in non-proxy/multi-origin deployments.

## Fix Applied
In `frontend/src/lib/connectivity.js`:
- derived probe URL from `import.meta.env.VITE_API_BASE_URL`
- normalized trailing slash handling
- fallback to relative `/api/health` when base is not configured

```js
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const base = API_BASE.replace(/\/$/, '')
const PROBE_URL = base ? `${base}/api/health` : '/api/health'
```

## Why This Fix Was Chosen
- Keeps probe path consistent with actual API traffic origin.
- Preserves local-dev relative behavior.

## Files Changed
- `frontend/src/lib/connectivity.js`

## Verification
- Targeted static check confirms probe now derives from `VITE_API_BASE_URL`.
- `syncStore` already uses `VITE_API_BASE_URL` for submit/sync requests (`frontend/src/stores/syncStore.js`).
