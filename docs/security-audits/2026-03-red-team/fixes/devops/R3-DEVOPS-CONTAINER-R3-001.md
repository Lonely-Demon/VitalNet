# Fix Log: R3-DEVOPS-CONTAINER-R3-001

- **Unit ID:** R3-DEVOPS-CONTAINER-R3-001
- **Title:** PR workflow exposes privileged secrets to untrusted code
- **Status:** completed

## Remediation

Refactored CI so pull request jobs run without injected repository secrets.
All PR jobs use placeholder/public-safe environment values only.

## Files Modified

- `.github/workflows/ci.yml`
