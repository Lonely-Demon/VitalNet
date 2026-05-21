# Fix Log: UNRESOLVED-DEVOPS-ENV-R3-007

- **Unit ID:** UNRESOLVED-DEVOPS-ENV-R3-007
- **Title:** CI Frontend Build Is Staging-Pinned at Compile Time
- **Status:** completed

## Evidence

- `.github/workflows/ci.yml:96-103` — push build uses `vars.VITE_API_BASE_URL` rather than a hardcoded staging URL.

## Remediation

- Replaced hardcoded staging endpoint with environment-scoped base URL variable

## Files Modified

- `.github/workflows/ci.yml`
