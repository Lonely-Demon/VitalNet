# Fix Log: R3-DEVOPS-INFRA-R3-001

- **Unit ID:** R3-DEVOPS-INFRA-R3-001
- **Title:** Public Health Check Becomes an Anonymous Internal-State Oracle
- **Status:** completed

## Remediation

Reduced sensitive health-surface disclosure by environment:

- In production/staging, health details are sanitized to coarse status indicators (`connected` / `error`).
- Added explicit schema and endpoint-status surface without exposing full internal exception strings.

## Files Modified

- `backend/app/main.py`
