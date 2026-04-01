# Fix Log: R3-DEVOPS-DR-R3-003

- **Unit ID:** R3-DEVOPS-DR-R3-003
- **Title:** Health check can go green after a bad restore
- **Status:** completed

## Remediation

Extended `/api/health` with schema compatibility probing against `case_records`
to ensure restored database shape is actually compatible with runtime expectations.

Health now degrades when schema probe fails.

## Files Modified

- `backend/app/main.py`
