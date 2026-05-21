# Fix Log: R3-DEVOPS-INFRA-R3-002

- **Unit ID:** R3-DEVOPS-INFRA-R3-002
- **Title:** Admin Control Plane Is Exposed on the Same Public API Edge
- **Status:** completed

## Evidence

- `backend/app/main.py:124-127` — admin router is only mounted when env policy allows it.
- `backend/app/main.py:235-248` — internal health route requires admin auth.

## Remediation

- Added admin route gate
- Added internal health route for privileged diagnostics

## Files Modified

- `backend/app/main.py`
- `backend/app/core/config.py`
