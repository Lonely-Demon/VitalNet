# @vitalnet/api

The Supabase Edge Function backend (Round 6 rebuild plan, Phase 3/4) — replaces the
FastAPI backend in `backend/app/` one endpoint tranche at a time, deployed as ONE edge
function (`api`) with a Hono router inside, per the official Supabase pattern (one
function per app, not one per route — avoids multiplying cold starts).

Runtime: Deno + Hono + [`jose`](https://github.com/panva/jose) for JWT/JWKS + the
`@supabase/supabase-js` client + `@vitalnet/clinical-core` (imported directly from
`packages/clinical-core/dist/`, Deno-native, no publish step) for the rules-first triage
engine + `web-push` (VAPID) for push notifications. No `package.json`/pnpm — Deno resolves
`npm:`/`jsr:` specifiers natively via `supabase/functions/api/deno.json`'s import map, and
is deployed with `supabase functions deploy`, not this repo's pnpm workspace tooling.

## Layout

```
supabase/functions/api/
  index.ts              # Hono app entrypoint — middleware wiring + route mounting
  deno.json              # import map (hono, jose, @supabase/supabase-js, zod, web-push, @vitalnet/clinical-core, @std/assert)
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
    cases.ts               # case row-authorization (3-way role check) + sanitization + risk-driver formatting (Phase 4)
    model.ts               # bundles the trained advisory tree model (_shared/models/*.json) for triage() (Phase 4)
    llm.ts                 # 4-tier Groq/Gemini fallback: briefing, patient-summary, protocol-answer (Phase 4)
    prompts.ts              # static system-prompt text ported from backend/prompts + protocol_knowledge.md (Phase 4)
    voice.ts                # Groq Whisper -> Sarvam AI transcription fallback (Phase 4)
    webpush.ts               # VAPID web push send (via the "web-push" npm package) — FLAGGED, see its header (Phase 4)
  routes/                  # health, outbreak, supervisor, referral, metrics, protocol, analytics,
                            # cases, security, dsr, admin, push, voice (Phase 4)
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

## Status (Phase 3 Tranche A + Phase 4 Tranche B — both complete)

**Tranche A** (read-mostly): middleware stack (CORS, security headers, correlation id,
CSRF/device guard, rate limiting, hybrid JWT auth with per-isolate profile caching),
`/api/health`, `GET /api/outbreak/signals` (EARS C1 aberration signals, ported to
`_shared/ears.ts` — calls `fn_outbreak_signal_counts` via `.rpc()`, facility-scoped via
`_shared/scoping.ts`), `GET /api/supervisor/team-metrics` (`_shared/teamMetrics.ts` —
calls `fn_team_metrics`), `GET /api/facilities` (referral target picker,
`_shared/facilities.ts` — calls `fn_open_case_counts`), `GET /api/referrals` (RLS-scoped
list, no RPC needed), `GET /api/metrics` (admin-only; `_shared/prometheus.ts` hand-formats
the Prometheus text exposition format), `GET /api/protocol/questions` (genuine Postgres
RLS, no RPC — `protocol_questions` carries no PHI), and all five `analytics` endpoints
(`GET /summary`, `/emergency-rate`, `/response-times`, `/ml-agreement`, `/export`).
`/summary` runs 5 queries concurrently with a per-query timeout and graceful degradation
(`_shared/queryTimeout.ts`). `/export` streams a CSV (`_shared/csv.ts`) and writes a PHI
audit log entry. The percentile/median math (`_shared/analyticsStats.ts`) required
matching Python's round-half-to-even `round()` exactly — `Math.round()` disagrees at exact
`.5` index boundaries (caught by a test, see that file's `pythonRound` comment).

**Tranche B** (writes + the rules-first flip — the Round 6 rebuild plan's centerpiece):

- **`POST /api/submit` now computes `triage_level` via `@vitalnet/clinical-core`'s
  `triage()` in `rules_first` mode** (`routes/cases.ts`) — the deterministic rules engine
  (`packages/clinical-core/src/rules/engine.ts`) is the SOLE source of `triage_level`,
  replacing the Python backend's ML-authoritative `predict_triage()`. The advisory tree
  model (bundled from the same trained artifact apps/web fetches, copied into
  `_shared/models/*.json` — see `_shared/model.ts`) runs alongside and contributes
  `model_tier`/`model_agreed`/confidence as ADVISORY fields only
  (`phase29_events_and_advisory_model.sql`'s `model_tier`, `rules_fired`, `model_agreed`
  columns) — it never influences the tier. `risk_driver` is now built from the rules
  engine's fired-rule audit trail with citations (`_shared/cases.ts::formatRiskDriver`),
  replacing the old SHAP-prose explanation — strictly more auditable, since every clause
  is a citable rule id rather than a black-box feature attribution. The LLM briefing
  (`_shared/llm.ts`, 4-tier Groq/Gemini fallback via `fetch`, not an SDK) still hard-locks
  `triage_level`/`disclaimer` on every output path, and the EMERGENCY push-alert fires as
  a backgrounded task (`EdgeRuntime.waitUntil`) exactly as before.
- The rest of `cases.ts`: `GET /api/cases` (composite-keyset cursor pagination),
  `PATCH .../review`, `PATCH .../triage-override`, `PATCH .../outcome`, `GET .../mine`,
  `GET .../by-patient-key/:key`, `GET .../:id` (detail), `POST .../:id/patient-summary`.
- `routes/security.ts`: `DELETE /api/security/cases/:id` (soft-delete, `X-Device-Id`
  required).
- `routes/dsr.ts`: the DPDP Act 2023 data-subject-request lifecycle — export/erase/
  purge-expired, admin-mediated, anonymization via a redaction marker rather than hard
  delete.
- `routes/admin.ts`: full user CRUD (incl. bulk CSV onboarding with per-row rollback),
  facility CRUD (optimistic-concurrency toggle), stats, paginated audit log.
- `routes/push.ts` + `_shared/webpush.ts`: subscribe/unsubscribe/check-emergency-
  escalations, and the VAPID send itself via the `web-push` npm package (Deno npm compat)
  — **flagged as the highest-risk port**: no live network test coverage exists (by
  design, same posture as every other network-dependent piece in this suite); run a
  send-to-self integration test against a real push subscription before cutting this over.
- `routes/voice.ts` + `_shared/voice.ts`: multipart upload -> Groq Whisper (tried first)
  -> Sarvam AI (fallback only) via `fetch`, mirroring `app/services/voice.py`'s provider
  ordering exactly.
- `routes/protocol.ts` gained `POST /ask` and `PATCH /questions/:id/curate` (deferred from
  Tranche A since they needed `_shared/llm.ts::generateProtocolAnswer` to exist first) —
  deliberately isolated from the triage-briefing LLM call path (see `_shared/llm.ts`'s
  module header) so a protocol-assistant question can never be confused with, or
  influence, a triage decision.
- **Frontend cutover map** (`apps/web/src/api/base.js`): every Tranche B endpoint now has
  an `ENDPOINT_BACKEND` key (still `'legacy'` by default) and is wired into its calling
  domain module (`cases.js`, `admin.js`, `voice.js`, `protocol.js`, `push.js`,
  `stores/syncStore.js`'s `submitCase`/`processQueue`) via `apiBase()` — cutting any one
  endpoint over to the edge function is still a one-line flip, one-line rollback.
- **Not in this pass**: referral write endpoints (facility-capacity PATCH, create-referral
  POST, advance-status PATCH) — `referral.ts`'s own Tranche-A header called these out as
  Tranche B, but they weren't part of the plan's explicit Phase 4 endpoint list and
  weren't read/ported this round; still served by the legacy backend. Also out of scope:
  Phase 5's unified offline outbox (submissions still use the single-purpose
  `submission_queue`, not a generic `client_events`-backed outbox) and the frontend's own
  cutover from its mirrored clinical-logic files to `@vitalnet/clinical-core`.

The legacy FastAPI backend stays deployable and authoritative until each endpoint is
individually cut over via the base-URL resolver map.

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
