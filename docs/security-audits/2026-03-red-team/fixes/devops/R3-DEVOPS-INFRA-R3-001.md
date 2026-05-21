# Fix Log: R3-DEVOPS-INFRA-R3-001

- **Unit ID:** R3-DEVOPS-INFRA-R3-001
- **Title:** Public Health Check Becomes an Anonymous Internal-State Oracle
- **Status:** completed

## Evidence

- `backend/app/main.py:220-232` — public `/api/health` returns only `status` and `version`, plus short-lived cache headers.
- `backend/app/main.py:235-248` — internal health route is admin-authenticated and returns full diagnostics.

## Remediation

- Minimized anonymous health surface
- Split internal diagnostics to `/api/internal/health`

## Files Modified

- `backend/app/main.py`
