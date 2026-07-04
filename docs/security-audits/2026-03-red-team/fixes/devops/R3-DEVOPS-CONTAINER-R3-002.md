# Fix Log: R3-DEVOPS-CONTAINER-R3-002

- **Unit ID:** R3-DEVOPS-CONTAINER-R3-002
- **Title:** GitHub Actions are not pinned to immutable revisions
- **Status:** completed

## Remediation

Pinned all workflow actions in CI to immutable commit SHAs (not mutable tags).

## Files Modified

- `.github/workflows/ci.yml`
