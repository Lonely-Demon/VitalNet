# Fix Log: R3-DEVOPS-CICD-R3-004

- **Unit ID:** R3-DEVOPS-CICD-R3-004
- **Title:** Python dependency resolution is non-hermetic in secret-bearing CI jobs
- **Status:** completed

## Remediation

- Removed secret-bearing CI execution for PRs and pushes.
- Added deterministic install behavior with explicit pip upgrade and `--no-cache-dir`.
- Kept dependency installation anchored to `backend/requirements.txt` and explicit tooling pins where needed.

## Files Modified

- `.github/workflows/ci.yml`
