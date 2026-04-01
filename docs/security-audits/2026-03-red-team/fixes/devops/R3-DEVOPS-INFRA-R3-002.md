# Fix Log: R3-DEVOPS-INFRA-R3-002

- **Unit ID:** R3-DEVOPS-INFRA-R3-002
- **Title:** Admin Control Plane Is Exposed on the Same Public API Edge
- **Status:** completed

## Remediation

Added runtime gate for admin router inclusion:

- New config flag `ADMIN_API_ENABLED`
- Admin routes are only mounted when explicitly enabled

This enables deployment-time separation of admin control plane from public API surfaces.

## Files Modified

- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/.env.example`
