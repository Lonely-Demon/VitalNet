# Fix Log: R3-DEVOPS-MONITOR-R3-002

- **Unit ID:** R3-DEVOPS-MONITOR-R3-002
- **Title:** Health coverage misses the clinician write path and RLS-scoped auth path
- **Status:** completed

## Evidence

- `backend/app/main.py:176-199` — schema probe + optional RLS probe in health logic.

## Remediation

- Added schema compatibility probe for restore safety
- Added optional RLS-scoped auth-path probe

## Files Modified

- `backend/app/main.py`
- `backend/app/core/database.py`
