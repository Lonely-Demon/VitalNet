# Fix Log: UNRESOLVED-DEVOPS-ENV-R3-004

- **Unit ID:** UNRESOLVED-DEVOPS-ENV-R3-004
- **Title:** Reachability Probe Uses a Different Base URL Than API Traffic
- **Status:** completed

## Remediation

Aligned connectivity probe and API client URL construction semantics:

- Probe now derives from normalized `VITE_API_BASE_URL`
- API client/store modules use normalized base and safe path builders
- Added exported probe URL helper for consistency checks in sync flows

## Files Modified

- `frontend/src/lib/connectivity.js`
- `frontend/src/stores/syncStore.js`
- `frontend/src/api/cases.js`
- `frontend/src/api/admin.js`
- `frontend/src/api/analytics.js`
