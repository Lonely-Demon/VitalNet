# Fix Log: R3-DEVOPS-CONTAINER-R3-003

- **Unit ID:** R3-DEVOPS-CONTAINER-R3-003
- **Title:** Railway deployment defines no explicit runtime resource caps
- **Status:** completed

## Remediation

Added explicit Uvicorn runtime guardrails in deployment start commands:

- `--workers ${WEB_CONCURRENCY:-2}`
- `--limit-concurrency ${UVICORN_LIMIT_CONCURRENCY:-200}`
- `--timeout-keep-alive 15`

Also enabled restart policy controls in `railway.toml`.

## Files Modified

- `backend/railway.toml`
- `backend/Procfile`
