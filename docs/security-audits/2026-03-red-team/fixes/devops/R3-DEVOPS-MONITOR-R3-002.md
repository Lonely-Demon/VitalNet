# Fix Log: R3-DEVOPS-MONITOR-R3-002

- **Unit ID:** R3-DEVOPS-MONITOR-R3-002
- **Title:** Health coverage misses the clinician write path and RLS-scoped auth path
- **Status:** completed

## Remediation

Expanded health checks to include:

- Schema compatibility probe for clinician-path-required columns
- Optional RLS-scoped auth path probe using a dedicated health probe token

This gives monitoring visibility into both baseline DB connectivity and auth-scoped path integrity.

## Files Modified

- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/main.py`
- `backend/.env.example`
