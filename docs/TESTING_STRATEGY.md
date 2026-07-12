# VitalNet — Testing Strategy

What's tested, at what layer, why, and how to run and extend each suite.
This is the companion to `docs/API_REFERENCE.md` (what the API does) and
`docs/DECISIONS.md` (why the system is shaped this way) — this doc is about
how we know it actually works and keeps working.

## Philosophy

Three things matter more than raw coverage percentage in this codebase:

1. **The online/offline triage guarantee is non-negotiable.** The single
   most important test property in this repo is: *the same patient data
   produces the same triage tier whether computed server-side in Python or
   client-side in JS.* Two dedicated parity-test pairs enforce this at two
   different layers (tree evaluation, feature engineering) — see below.
   Never weaken or skip these to "unblock" a PR; a failure here means
   offline and online triage can silently disagree, which is a patient-
   safety defect, not a test nuisance.
2. **Safety invariants are tested as properties, not examples.** Rather than
   "given this one hardcoded vector, assert EMERGENCY," `test_classifier_
   safety.py` and `test_admin_authz.py` assert structural guarantees across
   *every* case a category can produce (every extreme-vital combination;
   every route in a router file). This catches a whole class of future
   regressions (a new admin route added without the auth guard; a new
   extreme-vital combination the safety net doesn't cover) that
   example-based tests would miss entirely.
3. **Tests should run without a live Supabase project wherever possible.**
   `conftest.py` injects fake, JWT-*format* (but not real) credentials so
   module-level Supabase client construction succeeds offline. Only
   `test_e2e.py` and the Playwright spec genuinely need a live server +
   real project — everything else runs in CI with zero external
   dependencies.

## Backend

### Layer 1 — Classifier smoke test (`tests/test_direct.py`)
Fastest possible feedback loop when iterating on the ML model: loads the
committed `.pkl`, runs a handful of representative synthetic cases, prints
the result. No server, no database, no network.
```bash
cd backend && PYTHONPATH=. python tests/test_direct.py
```
Not part of the pytest CI job (it's a standalone script, kept in its
original print-driven style rather than converted — see AGENTS.md for why
new tests shouldn't follow this pattern going forward).

### Layer 2 — pytest suite (offline, CI-enforced)
```bash
cd backend && pytest tests/ --ignore=tests/test_e2e.py -v
```

| File | What it guarantees |
|---|---|
| `test_classifier_safety.py` | Property tests: no extreme-vital combination is ever non-EMERGENCY; the NEWS2 floor never yields ROUTINE on a concerning single vital; `low_confidence` is present and boolean on every prediction. |
| `test_admin_authz.py` | Walks every route registered in `admin_routes.py` and asserts it carries `require_role('admin')` — the *only* access boundary on the RLS-bypassing service-role client (`docs/DECISIONS.md` §7). A new admin route added without the guard fails this test, not silently ships a hole. |
| `test_feature_parity.py` | Replays `tests/fixtures/golden_feature_vectors.json` through `ClinicalFeatureEngineer` and asserts an exact (1e-6 tolerance) match — half of the online/offline guarantee (see Frontend layer below for the other half). Freezes the clock (`docs/DECISIONS.md` §12). |
| `test_bulk_user_import.py` | Row-isolation for CSV bulk onboarding — one bad row (weak password, missing facility) must not fail the batch, and a profile-provisioning failure must roll back the orphaned auth user. |
| `test_sms_parser.py` | Unit tests for the Tier-3 SMS-fallback scaffolding's fixed-format parser — pure logic, no mocking needed. |
| `test_scoping.py` | `resolve_facility_scope()` — the shared admin-global/role-owns-facility rule (`docs/DECISIONS.md` §25/§26). |
| `test_supervisor_routes.py` | `_aggregate_team_metrics()` — per-worker grouping, rate computation, sort order. |
| `test_outbreak_routes.py` | `_compute_ears_signals()` — floor enforcement, stable/noisy-baseline non-flagging, spike/zero-baseline flagging (`docs/DECISIONS.md` §26). |
| `test_protocol_answer.py` | `generate_protocol_answer()` — grounded/ungrounded contract, Groq→Gemini fallback, canned fallback, input sanitization (`docs/DECISIONS.md` §27). |

`conftest.py` sets fallback fake Supabase credentials (`setdefault` — a
real CI secret always wins) so the whole suite runs with zero network
access.

### Layer 3 — Full integration (`tests/test_e2e.py`)
```bash
cd backend && python tests/test_e2e.py
```
Needs a running `uvicorn` server and seeded Supabase test users (see
`Context/test_credentials.md`). Exercises real auth, real RLS, real
end-to-end request/response cycles. **Not** run in the unit-test CI job —
there's no live server available there. Run this locally before a release,
or in a dedicated staging-environment CI job if one gets added.

### Lint
```bash
cd backend && ruff check .
```
Zero-tolerance — CI fails on any finding.

## Frontend

### Online/offline parity (the other half of the non-negotiable guarantee)
```bash
cd frontend && npm run test:parity            # tree-evaluator vs. server model
cd frontend && npm run test:feature-parity     # feature engineering vs. server
```
Both are plain Node scripts (no test framework — deliberately zero-dependency
for something this CI-critical), reading the same golden-vector fixtures
the backend generates, replaying them through the JS implementations
(`treeEvaluator.js`, `triageClassifier.js::buildFeatureMap`), and asserting
an exact match. Both freeze `Date`/`datetime` to the same reference instant
as the backend (`docs/DECISIONS.md` §12) — **if you add a new
time-dependent engineered feature, extend the freeze in all three places
(`scripts/export_golden_vectors.py`, `tests/test_feature_parity.py`,
`frontend/tests/featureParity.test.mjs`) or these will intermittently fail**.

### Build
```bash
cd apps/web && pnpm build
```
Not "just a build" — it's the primary regression check for import errors,
bundle-size blowups (watch for a sudden jump in `dist/assets/*.js` sizes —
see CODEBASE_MAP.md §4's build-size notes), and PWA manifest/service-worker
generation issues.

### Playwright E2E (`tests/offline.spec.js`)
```bash
cd apps/web && pnpm exec playwright test tests/offline.spec.js
```
Drives a real browser through: login → go offline → fill and submit an
intake form → verify it queues → reconnect → verify it syncs. Needs a
running dev server (`pnpm dev`) and seeded test users against a real
Supabase project. Not part of CI for the same reason `test_e2e.py` isn't —
it needs a live environment.

### Accessibility scan (`tests/a11y.spec.js`)
```bash
cd apps/web && pnpm exec playwright test tests/a11y.spec.js
```
Runs `@axe-core/playwright`'s WCAG 2 A/AA ruleset against every role's main
screen. Unlike `offline.spec.js`, this one *is* wired into CI
(`a11y-frontend-pr`, PR-triggered) because it needs no live environment —
it uses `tests/helpers/mockBackend.js` to fake Supabase auth and the legacy
API via `page.route()` (the same mocked-auth technique documented above),
so it's safe to run on untrusted PR code with no secrets. See
`docs/ACCESSIBILITY.md` for what it's caught. Two of its tests wait a fixed
~1s before scanning to clear the login page's and intake form's CSS
entrance animations — Playwright's "visible" state doesn't wait for
`opacity: 1`, so scanning immediately catches elements mid-fade and axe
reports a false-positive contrast violation on the blended color; if you
add a new `animate-fade-up`/staggered-delay element to a scanned page and
this suite starts flaking, that's almost certainly why. It also needs
`packages/clinical-core` built first (`pnpm --filter @vitalnet/clinical-core
run build`) — `apps/web` imports its compiled `dist/`, which is gitignored
and only gets produced by an explicit build, not by `pnpm install
--ignore-scripts`; the CI job runs this as its own step since it's the only
PR-triggered job whose dev server actually needs the built package (
`build-frontend-pr` gets it for free as a side effect of its "clinical-core
tests" step's `pretest` hook).

### Ad hoc live-browser E2E in a sandbox with no direct internet access

Some agent sandboxes route outbound HTTPS through a policy proxy that
Chromium cannot use (confirmed: even a plain cross-origin navigation times
out, while server-side `httpx`/`curl` through the same proxy work fine —
see `docs/DECISIONS.md` §29). If you hit this while driving a real browser
against a live Supabase project:

1. Do a real login server-side (`POST {SUPABASE_URL}/auth/v1/token
   ?grant_type=password`) and a real profile fetch, via `httpx`/`curl` —
   these work because they go through the proxy correctly.
2. In Playwright, intercept exactly `**/auth/v1/token**` and
   `**/rest/v1/profiles**` with `page.route()` and fulfill them with that
   captured JSON. **Include explicit CORS response headers**
   (`Access-Control-Allow-Origin`/`-Methods`/`-Headers`) and handle the
   `OPTIONS` preflight — Chromium enforces CORS on `route.fulfill()`
   responses exactly like real ones; a preflight without them silently
   blocks the real request with no console error, which looks exactly
   like a hung backend and is easy to misdiagnose as one.
3. Leave every other route unmocked. Calls to your own backend (same-origin
   relative to the dev server's proxy config, or plain `localhost`) go
   over the real network — that's the part actually under test.
4. Abort `**/realtime/v1/**` (Supabase Realtime websockets) rather than
   let it hang; hooks using it are already designed to degrade without a
   live subscription.

This tests 100% of your own frontend/backend code paths for real; only the
third-party auth transport is faked, and it's faked with real captured
data, not fabricated data.

## What CI actually runs automatically

On every PR: `ruff check` (backend), the pytest suite minus `test_e2e.py`
(backend), `npm run build` (frontend), the `tests/a11y.spec.js` axe-core
scan (`a11y-frontend-pr`), CodeQL analysis (Python + JS/TypeScript +
GitHub Actions workflows). `offline.spec.js` is documented above as
something a contributor should run locally — check
`.github/workflows/ci.yml` for the exact current CI job list, since this
doc can drift from it (the workflow file is the source of truth for what
actually gates merges).

## Adding a new test

- **A new safety/invariant property** (something that should hold for an
  entire category of inputs, not one example): add it to
  `test_classifier_safety.py` following its existing pattern — generate or
  enumerate the input space, assert the invariant over all of it.
- **A new route's authorization**: if it's under `/api/admin`, it's already
  covered generically by `test_admin_authz.py` — no new test needed unless
  you're adding a *different* authorization pattern (e.g. a new
  facility-scoping rule), in which case write a focused unit test mocking
  the relevant Supabase calls (see `test_bulk_user_import.py` for the
  `unittest.mock.patch` pattern used to test route logic without a live DB).
- **A new engineered ML feature**: add it to both `clinical_features.py`
  and `triageClassifier.js`, regenerate the golden vectors
  (`python scripts/export_golden_vectors.py`), and confirm both parity
  tests still pass. If it's time-dependent, extend the clock freeze (see
  above).
- **A new endpoint**: add it to `docs/API_REFERENCE.md` in the same change;
  a dedicated test is optional unless it introduces new authorization logic
  or a new invariant worth guarding generically.

Prefer real `pytest`-style `assert`-based tests for anything new — the
print-driven standalone-script pattern (`test_direct.py`, `test_e2e.py`)
predates the current pytest suite and is kept for its specific
fast-feedback/full-integration purposes, not as a template for new tests.
