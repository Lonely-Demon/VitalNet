# VitalNet — Deployment and Preproduction Runbook

> **Scope:** Current repository and deployment workflow
>
> **Last verified:** 2026-08-22
>
> This runbook covers controlled promotion from `dev` to `test` and read-only
> preproduction verification. It does not authorize Production deployment,
> clinical use, real-patient-data testing, or activation of any governance-gated
> feature.

## Environment map

| Environment | Branch/project | Purpose | Allowed activity |
|---|---|---|---|
| Development | GitHub `dev` | Active engineering baseline | Code, documentation, synthetic tests, reviewed PRs |
| Preproduction | GitHub `test`; Vercel `vitalnet-preprod`; Render `vitalnet-preprod-api` | Controlled integration and acceptance testing | Synthetic fixtures, read-only health checks, explicitly authorized test accounts |
| Preview | Vercel `vital-net` Preview / Pre-Production | Build and preview verification | Non-production preview inspection; no Production selection |
| Production | GitHub `main`; production Vercel/Render/Supabase | Live service | Separate reviewed release process only |

The current `test` branch contains the verified refinement package. It must not
be treated as clinically validated or as permission to use real patient data.

## Required Vercel configuration

The repository is a pnpm workspace monorepo. The tracked root `vercel.json`
contains the repository-level build, output, install, and SPA-rewrite settings.
The separate `vital-net` Vercel project must additionally have these project
settings:

| Setting | Required value |
|---|---|
| Root Directory | `apps/web` |
| Include files outside the root directory in the Build Step | Enabled |
| Build Command override | `cd ../../packages/clinical-core && pnpm run build && cd ../../apps/web && pnpm run build` |
| Output Directory | `dist` when Root Directory is `apps/web` |
| Deployment environment for verification | Preview / Pre-Production |

The first two settings prevent the stale `frontend` path failure. The
workspace-aware Build Command generates the ignored `packages/clinical-core/dist`
artifact before Vite resolves the web package’s workspace import.

Do not select Production while repairing a Preview deployment. A project-level
setting update may affect future builds in all environments, but changing the
setting does not itself redeploy Production; verify the Production deployment
has not been replaced before declaring the operation complete.

## Promotion workflow

1. Confirm the source `dev` commit and worktree are clean. Review the diff from
   `origin/test` before opening a promotion PR. Never force-push `test` and do
   not overwrite test-specific preproduction history.
2. Open a PR from the validated promotion branch into `test`. The PR body must
   identify the source `dev` commit, the preserved test-specific commits, the
   test-only scope, the verification evidence, and the explicit exclusion of
   PR #116 or any other unapproved work.
3. Wait for the applicable GitHub checks. The known unrelated `Vercel –
   vital-net` baseline failure must be distinguished from failures in the
   `vitalnet-preprod` deployment or repository CI.
4. Squash-merge only after actionable checks pass. Do not promote to `main` as
   part of this procedure.
5. Confirm the final `test` commit and inspect the preproduction Vercel and
   Render deployment records. Record the result in the change or release note.

## Read-only smoke checks

These checks do not authenticate, submit a case, write to a database, or send a
patient payload:

```bash
# Preproduction frontend
curl -I --max-time 45 https://vitalnet-preprod.vercel.app/

# Preproduction API liveness
curl -sS --max-time 120 https://vitalnet-preprod-api.onrender.com/api/health

# Synthetic CORS preflight only
curl -i -X OPTIONS \
  -H 'Origin: https://vitalnet-preprod.vercel.app' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type,x-event-id' \
  --max-time 45 \
  https://vitalnet-preprod-api.onrender.com/api/submit
```

A successful health response demonstrates liveness only. It does not verify
authentication, RLS, migrations, triage correctness, LLM behavior, push
notifications, or clinical safety.

For a non-production preview, Vercel may require an authenticated browser
session and return a Vercel login page to unauthenticated `curl` requests. The
provider deployment status and authenticated preview view are the authoritative
checks for that protected preview.

## Keep-alive operations

The selected keep-alive scope is Supabase production and preproduction plus Render preproduction. Production Render is intentionally excluded. The version-controlled workflows are `.github/workflows/supabase-keepalive.yml` and `.github/workflows/backend-keepalive.yml`; scheduled execution uses the repository default branch.

The Supabase workflow runs every two days and performs one read-only request against `facilities` for each project. It uses `SUPABASE_URL`/`SUPABASE_ANON_KEY` for production and `TEST_SUPABASE_URL`/`TEST_SUPABASE_ANON_KEY` for preproduction. The response body is discarded. The Render workflow runs every ten minutes against `https://vitalnet-preprod-api.onrender.com/api/health` and sends no patient payload.

Required repository secret names must exist before scheduled Supabase runs perform activity. Use anonymous/publishable keys only; never substitute `SUPABASE_SERVICE_ROLE_KEY`. A missing secret causes the corresponding Supabase matrix entry to skip rather than exposing a credential or making an unsafe request.

The Render workflow is a best-effort cold-start mitigation, not a guaranteed uptime monitor. GitHub schedule delivery may be delayed beyond Render’s 15-minute Free-service idle window. Render’s Free workspace budget is shared across services, so the workflow deliberately does not target production Render. If preproduction cold-start latency becomes an acceptance requirement, use a paid Render instance or an independently managed uptime monitor after reviewing cost and access implications.

## What is not allowed in this runbook

Do not use real patient data, raw external clinical records, production
credentials, or live clinical workflows. Do not run evaluation scoring against
real data without a separate explicit authorization and gate. Do not change the
production model, rules, thresholds, API routing, database schema, or endpoint
cutover map as part of deployment troubleshooting. Do not activate the
paediatric advisory, rules-first Edge Function traffic, or unreviewed
Hindi/Tamil translations.

## Rollback and incident handling

If a preproduction build fails, first inspect the provider build logs and the
exact source commit. Correct only the configuration or code responsible for the
failure in a dev-targeted PR. If a successful preproduction deployment later
shows a regression, redeploy the last known-good `test` revision or revert via
a reviewed PR; never force-push a branch to hide the failure.

If a production deployment is ever affected unexpectedly, stop all further
promotion and follow `docs/INCIDENT_RESPONSE.md` and
`docs/DISASTER_RECOVERY.md`. A deployment that is Ready is not automatically
safe for clinical use; consult `docs/CLINICAL_GOVERNANCE.md`,
`docs/CLINICAL_REVIEW.md`, and the relevant evaluation boundary documents.

## Current recorded verification

The latest recorded test promotion used `test` commit `4fdeda6`. The corrected
`vital-net` Preview deployment `dpl_Ck13YQihn3c8piy1Ki9CBby78ckg` reached
`READY` after building `@vitalnet/clinical-core` and `@vitalnet/web`. The active
preproduction frontend returned HTTP 200, and the Render health endpoint
returned HTTP 200 with `status: ok` and version `0.3.0`.

These are historical operational checks, not a clinical validation result. Any
future deployment report must state its own commit, provider status, and test
scope rather than copying these values forward.
