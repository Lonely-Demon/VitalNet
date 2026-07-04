# Fix Log: UNRESOLVED-DEVOPS-ENV-R3-004

- **Unit ID:** UNRESOLVED-DEVOPS-ENV-R3-004
- **Title:** Reachability Probe Uses a Different Base URL Than API Traffic
- **Status:** completed

## Evidence

- `frontend/src/lib/connectivity.js:7-18` — probe URL now derives from normalized `VITE_API_BASE_URL`.
- `frontend/src/stores/syncStore.js:20,147,206` — submit/sync traffic uses the same normalized base URL.

## Remediation

- Aligned probe URL and API traffic base construction

## Files Modified

- `frontend/src/lib/connectivity.js`
- `frontend/src/stores/syncStore.js`
