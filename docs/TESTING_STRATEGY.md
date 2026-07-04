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
cd frontend && npm run build
```
Not "just a build" — it's the primary regression check for import errors,
bundle-size blowups (watch for a sudden jump in `dist/assets/*.js` sizes —
see CODEBASE_MAP.md §4's build-size notes), and PWA manifest/service-worker
generation issues.

### Playwright E2E (`tests/offline.spec.js`)
```bash
cd frontend && npx playwright test tests/offline.spec.js
```
Drives a real browser through: login → go offline → fill and submit an
intake form → verify it queues → reconnect → verify it syncs. Needs a
running dev server (`npm run dev`) and seeded test users. Not part of the
unit-test CI job for the same reason `test_e2e.py` isn't — it needs a live
environment.

## What CI actually runs automatically

On every PR: `ruff check` (backend), the pytest suite minus `test_e2e.py`
(backend), `npm run build` (frontend), CodeQL analysis (Python +
JS/TypeScript + GitHub Actions workflows). The tree/feature parity tests
and the Playwright spec are documented above as things a contributor should
run locally — check `.github/workflows/ci.yml` for the exact current CI
job list, since this doc can drift from it (the workflow file is the source
of truth for what actually gates merges).

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
