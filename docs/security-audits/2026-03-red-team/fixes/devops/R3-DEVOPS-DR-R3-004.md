# Fix Log: R3-DEVOPS-DR-R3-004

- **Unit ID:** R3-DEVOPS-DR-R3-004
- **Title:** Failover is blocked by single-endpoint architecture across API and database paths
- **Status:** completed

## Remediation

Implemented primary/failover database endpoint selection in runtime config and database client bootstrap:

- Added `SUPABASE_FAILOVER_URL`
- Added `SUPABASE_USE_FAILOVER`
- Centralized active endpoint selection and exposed endpoint metadata for health diagnostics

Also normalized frontend API base URL usage to avoid strict dependence on a single absolute origin.

## Files Modified

- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/main.py`
- `frontend/src/api/cases.js`
- `frontend/src/api/admin.js`
- `frontend/src/api/analytics.js`
- `frontend/src/stores/syncStore.js`
- `frontend/src/lib/connectivity.js`
- `backend/.env.example`
- `frontend/.env.example`
