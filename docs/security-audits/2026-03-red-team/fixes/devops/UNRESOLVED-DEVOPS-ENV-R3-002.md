# Fix Log: UNRESOLVED-DEVOPS-ENV-R3-002

- **Unit ID:** UNRESOLVED-DEVOPS-ENV-R3-002
- **Title:** Misspelled Env Vars Fail Open Instead of Failing Fast
- **Status:** completed

## Remediation

Configured strict environment validation:

- `pydantic-settings` now uses `extra='forbid'` to reject unknown env keys
- Added explicit startup validation requiring `ENVIRONMENT` to be present

This causes misconfiguration to fail fast during startup.

## Files Modified

- `backend/app/core/config.py`
