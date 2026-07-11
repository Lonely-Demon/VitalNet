# @vitalnet/api

The Supabase Edge Function backend (Round 6 rebuild plan, Phase 3/4) — replaces the
FastAPI backend in `backend/app/` one endpoint tranche at a time, deployed as ONE edge
function (`api`) with a Hono router inside, per the official Supabase pattern (one
function per app, not one per route — avoids multiplying cold starts).

Runtime: Deno + Hono + [`jose`](https://github.com/panva/jose) for JWT/JWKS + the
`@supabase/supabase-js` client. No `package.json`/pnpm — Deno resolves `npm:`/`jsr:`
specifiers natively via `supabase/functions/api/deno.json`'s import map, and is deployed
with `supabase functions deploy`, not this repo's pnpm workspace tooling.

## Layout

```
supabase/functions/api/
  index.ts              # Hono app entrypoint — middleware wiring + route mounting
  deno.json              # import map (hono, jose, @supabase/supabase-js, @std/assert)
  _shared/
    config.ts            # Deno.env settings, mirrors backend/app/core/config.py's field names
    database.ts           # Supabase client factories (anon/user-scoped/admin) + extractBearerToken
    auth.ts               # hybrid JWT verification + profile resolution + requireRole()
    functionPrefix.ts     # strips /functions/v1/api BEFORE Hono routes (cannot be middleware — see its header)
    correlationId.ts      # X-Request-ID propagation
    securityHeaders.ts    # hardening headers
    csrfDeviceGuard.ts     # CSRF token + X-Device-Id guard on state-changing /api requests
    rateLimit.ts           # fn_rate_limit-backed rate limiting, applied per-route with the FastAPI budgets
    audit.ts               # logPhiAccess/getClientIp (phi_audit_log, service-role, best-effort)
    queryTimeout.ts        # per-query timeout + graceful-degradation helper for analytics
  routes/                  # health, outbreak, supervisor, referral, metrics, protocol, analytics
  test/                    # deno test — see below
```

## Why this exists (vs. the FastAPI backend)

- **Cold starts**: a Render container idles down; an edge function's cold start is
  milliseconds, removing the `backend-keepalive.yml` workaround (Phase 6).
- **JWT verification that's actually fast for this project's signing algorithm**: the
  Python backend's fast path is local HS256 decode, which always misses (falling
  through to a network call) if the project uses Supabase's newer asymmetric signing
  keys — see `_shared/auth.ts`'s header comment. Here BOTH paths (HS256 local decode,
  JWKS local verify) are local and cached in-process; whichever matches the project's
  actual algorithm wins, with no network fallback left to be silently always-taken.
- **Rate limiting that survives a recycled isolate**: `slowapi`'s in-memory store
  doesn't persist across edge isolate instances. `fn_rate_limit` (a Postgres-backed
  token bucket, `backend/supabase/migrations/phase28_security_definer_fns.sql`) does.

## Status (Phase 3 Tranche A)

Done: middleware stack (CORS, security headers, correlation id, CSRF/device guard, rate
limiting, hybrid JWT auth with per-isolate profile caching), `/api/health`,
`GET /api/outbreak/signals` (EARS C1 aberration signals, ported to `_shared/ears.ts` —
calls `fn_outbreak_signal_counts` via `.rpc()`, facility-scoped via `_shared/scoping.ts`),
`GET /api/supervisor/team-metrics` (`_shared/teamMetrics.ts` — calls `fn_team_metrics`),
`GET /api/facilities` (referral target picker, `_shared/facilities.ts` — calls
`fn_open_case_counts`), `GET /api/referrals` (RLS-scoped list, no RPC needed),
`GET /api/metrics` (admin-only; `_shared/prometheus.ts` hand-formats the Prometheus text
exposition format — no per-request HTTP metrics yet, see `phase30_triage_metrics_fn.sql`'s
header for why that's a deliberate gap, not an omission), `GET /api/protocol/questions`
(genuine Postgres RLS, no RPC — `protocol_questions` carries no PHI), and all five
`analytics` endpoints (`GET /summary`, `/emergency-rate`, `/response-times`,
`/ml-agreement`, `/export`) — the last remaining Tranche A route module. `/summary` runs
5 queries concurrently with a per-query timeout and graceful degradation (`_shared/queryTimeout.ts`),
matching the Python original's `asyncio.gather`/`_run_query` pattern. `/export` streams a
CSV (`_shared/csv.ts`) and writes a PHI audit log entry via `_shared/audit.ts`'s
`logPhiAccess()` (service-role, one of the two legitimate remaining uses). The
percentile/median math (`_shared/analyticsStats.ts`) required matching Python's
round-half-to-even `round()` exactly — `Math.round()` disagrees at exact `.5` index
boundaries (caught by a test, see that file's `pythonRound` comment).

**Scope refinement from the original plan**: `protocol`'s `POST /ask` and
`PATCH /questions/:id/curate` are writes that also need `app/services/llm.py`'s 4-tier
Groq/Gemini fallback ported — moved to Tranche B (Phase 4) alongside `voice`, the other
LLM/external-API-heavy write surface, instead of force-fitting them into a "read-mostly"
tranche just because they share a Python module with the one read endpoint.

**Tranche A is now complete.** Not yet ported:
protocol's `/ask`+`/curate`, cases/security/dsr/admin/push/voice, and the rules-first
flip on `/api/submit` (Tranche B, Phase 4). The legacy FastAPI backend stays deployable
and authoritative for all of these until each is cut over — see the frontend's
per-endpoint base-URL resolver map (Phase 3 plan) for the rollback mechanism.

## Running locally

```sh
cd supabase/functions/api
SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_JWT_SECRET=... SUPABASE_SERVICE_ROLE_KEY=... \
  deno run --allow-net --allow-env index.ts
```

Or via the Supabase CLI once installed: `supabase functions serve api`.

## Testing

```sh
cd supabase/functions/api
deno test --allow-net --allow-env
deno fmt --check .
deno lint .
```

Tests are network-independent (see `test/auth.test.ts`'s header for what's deliberately
NOT covered this way — the JWKS/ES256 path requires a live Supabase project). Middleware
is tested via Hono's `app.request()` in-memory contract-test pattern (`test/middleware.test.ts`),
not a real HTTP server.
