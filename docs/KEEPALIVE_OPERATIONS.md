# VitalNet Keep-Alive Operations

> **Scope:** Keep the two Supabase projects active and keep only the preproduction Render backend warm. This document does not authorize production Render keep-alive traffic, production deployment, clinical use, or changes to the frozen model.

## Selected service targets

| Target | Public endpoint or project | Schedule | Purpose |
|---|---|---:|---|
| Render preproduction | `https://vitalnet-preprod-api.onrender.com/api/health` | Every 10 minutes | Reduce preproduction cold starts on the Render Free instance |
| Supabase production | `https://dlchgyndumbckprkyjrq.supabase.co/rest/v1/facilities?select=id&limit=1` | Every 2 days | Generate read-only database activity for the production project |
| Supabase preproduction | `https://amcwijezewymuviugwjy.supabase.co/rest/v1/facilities?select=id&limit=1` | Every 2 days | Generate read-only database activity for the preproduction project |
| Render production | Intentionally not targeted | None | Excluded by explicit product decision |

The Render target is the public, unauthenticated health endpoint. The Supabase targets issue a read-only PostgREST request against the public `facilities` table. The response body is discarded, so no facility or patient payload is emitted into Actions logs. No write, insert, update, delete, auth, or clinical endpoint is used.

## Why the frequencies differ

Render Free services spin down after 15 minutes without inbound traffic, so the preproduction request runs every 10 minutes as a best-effort attempt to remain inside that window. GitHub’s scheduler is not a strict real-time scheduler; delays can occur, so this workflow cannot guarantee the absence of cold starts. A paid Render instance is the reliable solution if preproduction latency becomes an acceptance requirement.

Supabase Free projects are candidates for pausing after roughly 7 days of insufficient database activity. A two-day read-only query cadence gives a multi-day margin for scheduler delays while avoiding needless database traffic.

## Required GitHub Actions configuration

The workflows are scheduled from the repository’s default branch. Repository configuration is therefore required on the branch that GitHub uses for scheduled execution.

| Name | Type | Required value or source |
|---|---|---|
| `TEST_SUPABASE_URL` | Repository secret | Preproduction project URL: `https://amcwijezewymuviugwjy.supabase.co` |
| `TEST_SUPABASE_ANON_KEY` | Repository secret | Existing preproduction anonymous/publishable key |
| `SUPABASE_URL` | Repository secret | Production project URL: `https://dlchgyndumbckprkyjrq.supabase.co` |
| `SUPABASE_ANON_KEY` | Repository secret | Production anonymous/publishable key |

The Render workflow in this dev-only correction uses the canonical preproduction URL directly and does not require a secret or variable. The production Render service is intentionally absent.

The anonymous Supabase keys are the least-privilege choice for this read-only request. Do not replace them with `SUPABASE_SERVICE_ROLE_KEY`; a service-role key is broader than necessary and would increase the impact of an accidental workflow or log exposure.

## Verification

A successful Render keep-alive run must report an HTTP status from 200 through 399 for the preproduction `/api/health` endpoint. A successful Supabase run must report an HTTP status from 200 through 399 for each project. The Actions step discards response bodies and logs only the target name and HTTP status.

A health response demonstrates liveness only. It does not verify authentication, RLS correctness, migrations, triage correctness, LLM behavior, push notifications, or clinical safety. A successful database request demonstrates database reachability/activity only; it does not validate the application’s data-access policies.

## Free-tier limitations

Render’s official Free-tier documentation states that a Free web service spins down after 15 minutes without inbound traffic and that the workspace receives 750 Free instance hours per calendar month. This project has two Free backend services, so keeping both warm continuously would require approximately 1,440 service-hours in a 30-day month and exceed the shared allowance. This plan therefore keeps only preproduction on the best-effort workflow and leaves production Render untouched.

Supabase’s official documentation states that Free projects showing low activity over a 7-day period may be paused. The two-day schedule is intended to keep both projects active, but it cannot override account suspension, quota exhaustion, provider outages, or a disabled key.

## Sources

1. [Render — Deploy for Free](https://render.com/docs/free)
2. [Supabase — Project Pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
3. [Supabase — Pricing](https://supabase.com/pricing)
4. [GitHub — Events that trigger workflows](https://docs.github.com/actions/using-workflows/events-that-trigger-workflows)
