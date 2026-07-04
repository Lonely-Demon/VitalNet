# Remediation Log: R3-DEVOPS-CICD-R3-001

## Unit ID and Title
**Unit ID:** R3-DEVOPS-CICD-R3-001  
**Title:** Secrets are injected into PR jobs that execute repo-controlled code

## Status
completed

## Evidence

- `.github/workflows/ci.yml:17-56` — PR jobs (`lint-backend`, `build-frontend-pr`) run without repository secrets.
- `.github/workflows/ci.yml:58-103` — secret-bearing jobs are limited to `push` events.

## Fix Applied

- Split PR and push workflows with `if: github.event_name == 'pull_request'` / `push`
- Removed secrets from PR-context jobs
- Kept backend tests and production build on push-only jobs

## Files Modified

- `.github/workflows/ci.yml`
