# Fix Log: R3-DEVOPS-CONTAINER-R3-006

- **Unit ID:** R3-DEVOPS-CONTAINER-R3-006
- **Title:** CI workflow has no timeout or run-concurrency guardrails
- **Status:** completed

## Remediation

Added workflow-level and job-level controls:

- Workflow `concurrency` group + `cancel-in-progress: true`
- Job `timeout-minutes` for all CI jobs

## Files Modified

- `.github/workflows/ci.yml`
