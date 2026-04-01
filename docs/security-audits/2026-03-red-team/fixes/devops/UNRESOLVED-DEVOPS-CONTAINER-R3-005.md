# Fix Log: UNRESOLVED-DEVOPS-CONTAINER-R3-005

- **Unit ID:** UNRESOLVED-DEVOPS-CONTAINER-R3-005
- **Title:** Image hardening posture is not enforceable in current Nixpacks deployment
- **Status:** blocked

## Blocker

Current deployment uses Railway Nixpacks without a project Dockerfile/image hardening pipeline.
Hardening controls requested by the finding (base image pinning, non-root image user, package hardening, image scanning policy) cannot be fully enforced from `railway.toml` alone.

## Partial Mitigations Applied

- Runtime worker/concurrency guardrails added (`uvicorn` flags)
- Restart policy controls added in Railway deploy config

## Recommended Follow-up

Adopt explicit Dockerfile-based deploy path and enforce image policy in CI (scan + signed image + pinned digest).

## Files Modified

- `backend/railway.toml`
- `backend/Procfile`
