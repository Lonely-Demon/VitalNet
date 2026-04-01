# Fix Log: R3-DEVOPS-CICD-R3-002

- **Unit ID:** R3-DEVOPS-CICD-R3-002
- **Title:** GitHub Actions are referenced by mutable release tags
- **Status:** completed

## Remediation

Pinned workflow actions to immutable commit SHAs:

- `actions/checkout` → `34e114876b0b11c390a56381ad16ebd13914f8d5`
- `actions/setup-python` → `a26af69be951a213d495a4c3e4e4022e16d87065`
- `actions/setup-node` → `49933ea5288caeca8642d1e84afbd3f7d6820020`

## Files Modified

- `.github/workflows/ci.yml`
