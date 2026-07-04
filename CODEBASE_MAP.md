# VitalNet — Codebase Map

**Purpose of this document**: a single, current, high-signal reference so a
future contributor (human or AI agent) can orient in VitalNet without
re-reading the entire codebase. If you make a structural change (new
directory, new major module, a file moves, a data flow changes), **update
this document in the same commit**. Stale maps are worse than no map —
see the "Keeping this document current" section at the bottom for the
specific rule.

Last verified against the codebase: 2026-07-04 (post round-2 enterprise
hardening — hybrid auth, pure-JS offline engine, ML safety layers — see git
log for the full change list).

---

## 1. What VitalNet is, in one paragraph

An offline-first clinical triage PWA for rural Indian healthcare. ASHA
(community health) workers fill out a patient intake form — works with or
without connectivity. A local ML classifier (same model, running either in
Python server-side or as ONNX in the browser) instantly assigns EMERGENCY /
URGENT / ROUTINE. An LLM (Groq, with Gemini fallback) generates a
structured clinical briefing for the case. Doctors see a real-time,
priority-sorted dashboard of incoming cases and mark them reviewed. Admins
manage users and facilities. Three roles, enforced by both backend checks
and Supabase Row Level Security.

## 2. Repository layout

```
VitalNet/
├── backend/            FastAPI Python app — see §3
├── frontend/           React 19 + Vite PWA — see §4
├── database/           Supabase SQL setup scripts (NOT the full schema — see §5)
├── colab/              Legacy Google Colab training script — historical reference only,
│                       NOT wired into the app, trains on only 14 raw features (predates
│                       ClinicalFeatureEngineer). Do not use its output as a production model.
├── Context/            Historical phase-by-phase planning documents from earlier
│                       development sprints. Read for history/rationale, not current state.
├── .github/workflows/  CI (ci.yml) — backend pytest + frontend build, on PRs to main
├── README.md           Setup, features, deployment — start here
├── AGENTS.md           Conventions for coding agents working in this repo
├── CODEBASE_MAP.md     This file
├── FEATURES_ROADMAP.md Proposed feature backlog with implementation-ready specs
└── {ARCHITECTURE_RESTRUCTURE,REBUILD_INSTRUCTIONS,IMPROVEMENTS}.md
                        Historical execution logs from past hardening phases — all marked
                        [!NOTE] superseded-by-this-file at the top. Useful for "why is it
                        built this way" archaeology, not for "what does it do today."
```

## 3. Backend (`backend/`)

FastAPI, Python 3.13 (target; 3.11+ works for local dev), Supabase
(PostgreSQL + Auth + Realtime) as the only database, Groq/Gemini for LLM
briefings, scikit-learn for ML triage.

```
backend/
├── app/
│   ├── main.py                     Entry point ONLY: logging setup, lifespan (loads
│   │                                the ML classifier once), CORS, rate-limiter wiring,
│   │                                router registration, global exception handlers,
│   │                                /api/health. No route logic lives here.
│   ├── core/
│   │   ├── config.py                Pydantic Settings — all env vars, fails fast at
│   │   │                            import if required vars are missing. Round-2
│   │   │                            adds: jwt_local_verification, revocation_
│   │   │                            recheck_seconds, rate_limit_storage_uri,
│   │   │                            security_headers_hsts.
│   │   ├── auth.py                  HYBRID JWT verification: verifies signature/
│   │   │                            exp/aud LOCALLY (HS256 via jwt_secret) on the
│   │   │                            hot path — no Supabase round-trip per request —
│   │   │                            with a network get_user() fallback for
│   │   │                            asymmetric-key projects. Short-TTL is_active/
│   │   │                            revocation re-check cuts off deactivated users
│   │   │                            within revocation_recheck_seconds (previously
│   │   │                            the backend never checked is_active at all).
│   │   │                            Also exposes verify_sub_for_rate_limit().
│   │   │                            require_role(*roles) dependency factory.
│   │   ├── database.py              Three Supabase clients: supabase_anon (public
│   │   │                            reads), get_supabase_for_user() (RLS-scoped,
│   │   │                            per-request), supabase_admin (service_role,
│   │   │                            auth.admin.* ONLY — never for case_records/profiles).
│   │   └── logging.py                JSON structured logging setup (setup_logging()),
│   │                                 called first in main.py.
│   ├── api/routes/
│   │   ├── cases.py                  /api/submit, /api/cases, /api/cases/{id}/review,
│   │   │                             /api/cases/mine, /api/cases/{id}. Owns the shared
│   │   │                             slowapi `limiter` instance (imported by the other
│   │   │                             two route modules). Doctor case list is
│   │   │                             facility-scoped for 'doctor' role, global for
│   │   │                             'admin' — see §5's role-scoping note.
│   │   ├── admin_routes.py           /api/admin/* — user CRUD, facility CRUD, system
│   │   │                             stats. All admin-only (require_role('admin')),
│   │   │                             all rate-limited.
│   │   └── analytics_routes.py       /api/analytics/* — aggregate stats, EMERGENCY
│   │                                  rate trend. Facility-scoped for 'doctor',
│   │                                  global for 'admin' (GLOBAL_SCOPE_ROLE constant).
│   ├── models/schemas.py            Pydantic request/response models. IntakeForm is
│   │                                 the case-submission contract — every field is
│   │                                 bounded (min/max length, numeric ranges, enums)
│   │                                 and free-text fields are control-character-stripped.
│   │                                 If you add a field here, add a matching bound to
│   │                                 frontend/src/utils/validation.js.
│   ├── ml/
│   │   ├── README.md                 ML architecture + clinical grounding — READ
│   │   │                             before touching classifier.py / clinical_features.py.
│   │   ├── MODEL_CARD.md              Intended use, metrics (and what they do/don't
│   │   │                             mean), limitations, ethics — the honest record.
│   │   ├── classifier.py             Public ML API: load_classifier(), predict_triage()
│   │   │                             / run_triage(), get_classifier_info(). Three
│   │   │                             layers per prediction: (1) _safety_net_check →
│   │   │                             EMERGENCY for extreme vitals/critical symptoms,
│   │   │                             (2) the trained model, (3) _news2_concerning_vital
│   │   │                             floor → never ROUTINE on a concerning vital.
│   │   │                             Also emits a low_confidence abstention flag.
│   │   ├── clinical_features.py     ClinicalFeatureEngineer — expands ~14 raw intake
│   │   │                             fields into 45 engineered features. MIRRORED in
│   │   │                             JS (frontend triageClassifier.js). The safety
│   │   │                             net + floor are mirrored in JS clinicalRules.js.
│   │   │                             Change one side → change the other → retrain →
│   │   │                             `npm run test:parity` (CI-enforced).
│   │   └── models/triage_classifier.pkl
│   │                                 The trained model + SHAP explainer bundle.
│   │                                 Regenerate via scripts/train_classifier.py — never
│   │                                 hand-edit.
│   ├── services/llm.py              4-tier LLM fallback (Groq 70B → Groq 8B → Gemini
│   │                                 Flash → Gemini Flash-Lite) for clinical briefings.
│   │                                 triage_level and disclaimer are hard-locked onto
│   │                                 every LLM output regardless of tier
│   │                                 (_enforce_schema()) — no LLM call can change the
│   │                                 triage decision. Free-text patient fields are
│   │                                 sanitised before entering the prompt
│   │                                 (_sanitize_field()) to resist prompt injection.
│   └── __init__.py files (package markers, no logic)
├── scripts/
│   ├── train_classifier.py          THE training entrypoint (single unified model —
│   │                                 see app/ml/README.md). One run outputs the
│   │                                 backend .pkl, frontend triage_trees.json +
│   │                                 features_config.json, and the golden-vector
│   │                                 fixture; asserts pkl==onnx==tree-JSON parity;
│   │                                 reports 5-fold CV + calibration (ECE).
│   └── tree_export.py                Converts the (in-memory) ONNX tree ensemble to
│                                     the compact triage_trees.json + a Python
│                                     reference evaluator used for the parity assert.
├── prompts/clinical_system_prompt.txt
│                                     System prompt for the LLM briefing generator.
├── tests/
│   ├── conftest.py                   Sets fallback fake (JWT-format) Supabase creds so
│   │                                 unit tests run offline; real CI secrets win.
│   ├── test_direct.py                Classifier smoke tests, no server/DB required.
│   ├── test_classifier_safety.py     Property tests for the safety guarantees (extreme
│   │                                 vitals → EMERGENCY; concerning vital never ROUTINE;
│   │                                 low_confidence present). Run in CI.
│   ├── test_admin_authz.py           Asserts every /api/admin route is require_role
│   │                                 ('admin')-guarded (the only boundary on the RLS-
│   │                                 bypassing service-role client). Run in CI.
│   └── test_e2e.py                   Full integration test against a running server +
│                                     real Supabase auth (needs seeded test users).
│                                     NOT run in unit CI (needs a live server).
├── seed_user.py                      One-off script to create/fix a test doctor
│                                     account. Mutates your Supabase project directly.
├── requirements.txt                  Runtime dependencies. scikit-learn and shap are
│                                     pinned to EXACT versions — see the comments in
│                                     the file and app/ml/README.md for why.
├── requirements-train.txt            ONLY needed to run scripts/train_classifier.py
│                                     (skl2onnx, onnxruntime) — NOT installed in
│                                     production; keeps the deploy footprint small.
├── Procfile / railway.toml / runtime.txt
│                                     Railway deployment config.
└── CLASSIFIER_CHANGELOG.md           ML model version history.
```

### Backend request lifecycle (submit case, the core flow)

1. `POST /api/submit` (`cases.py::submit_case`) — rate-limited 20/min/user,
   `require_role('asha_worker', 'admin')`.
2. `IntakeForm` Pydantic validation (bounds, symptom allow-list, control-char
   stripping).
3. `run_triage(form_data)` (`classifier.py`) — safety-net check first, then
   the trained model + SHAP explanation if the safety net didn't trigger.
4. `generate_briefing(form_data, triage_result)` (`llm.py`) — 4-tier LLM
   fallback; triage_level is locked onto the output regardless of which
   tier (or none) succeeded.
5. Upserted into `case_records` via a user-scoped Supabase client
   (`get_supabase_for_user`) using `client_id` as the idempotency key
   (`on_conflict="client_id", ignore_duplicates=True"`) — this is what makes
   offline-queue retries safe.
6. Supabase Realtime pushes the INSERT to any subscribed doctor dashboards
   (`useRealtimeCases` on the frontend).

## 4. Frontend (`frontend/`)

React 19, Vite 7, Tailwind CSS v4, `vite-plugin-pwa` for offline/installable
support, no TypeScript (plain `.jsx`/`.js`).

```
frontend/src/
├── main.jsx                  Entry point — mounts <App/>, registers the PWA service worker.
├── App.jsx                   Role-based routing (no react-router — just profile.role
│                              branching). Panels are React.lazy()-loaded per role so a
│                              given user only downloads their own panel's code.
├── store/authStore.jsx       AuthProvider/useAuth — Supabase session + profile state.
├── lib/
│   ├── supabase.js            Supabase client — IndexedDB-backed session storage
│   │                          (survives memory pressure better than localStorage on
│   │                          low-RAM Android tablets).
│   ├── api.js                 Backward-compat barrel re-exporting from api/*.js and
│   │                          stores/syncStore.js — prefer importing from the
│   │                          specific module directly in new code.
│   ├── connectivity.js        isServerReachable() — real backend health-check probe,
│   │                          NOT navigator.onLine (which only checks local interface,
│   │                          not actual backend reachability — critical for rural
│   │                          satellite-link scenarios).
│   └── offlineQueue.js        IndexedDB submission queue (enqueue/dequeue/getAllQueued),
│                              shared DB with useDraftSave.js.
├── stores/syncStore.js        submitCase() (online+offline paths) and processQueue()
│                              (drains the offline queue with a paced delay to stay
│                              under the backend rate limit).
├── api/{auth,cases,admin,analytics}.js
│                              Stateless fetch wrappers per domain, all via authHeaders().
├── hooks/
│   ├── useLocalTriage.js      Wires up offline-model warmup (triggered on offline/
│                              unreachable events) and classify().
│   ├── useDraftSave.js        Auto-saves IntakeForm state to IndexedDB keyed by
│                              client_id (survives tab eviction on low-RAM devices).
│   └── useRealtimeCases.js    Supabase Realtime subscription wrapper (INSERT/UPDATE),
│                              used by Dashboard, ASHAPanel history, AnalyticsDashboard.
├── utils/
│   ├── triageClassifier.js    Offline triage orchestrator (NO onnxruntime). Loads
│   │                          /models/triage_trees.json + features_config.json;
│   │                          layered: safetyNetCheck → tree eval → NEWS2 floor →
│   │                          low_confidence, with a rules-only fallback if the model
│   │                          can't load (triage never fails). buildFeatureMap()
│   │                          MIRRORS backend clinical_features.py; feature ORDER is
│   │                          fetched from features_config.json (never hard-coded).
│   ├── treeEvaluator.js       ~120-line dependency-free evaluator for the tree JSON —
│   │                          a 1:1 port of scripts/tree_export.py::evaluate_tree_json.
│   ├── clinicalRules.js       safetyNetCheck() + news2ConcerningVital() — 1:1 mirror
│   │                          of the deterministic rules in classifier.py.
│   └── validation.js          Zod schema — MUST mirror the bounds in
│                              backend/app/models/schemas.py::IntakeForm.
├── pages/
│   ├── LoginPage.jsx, IntakeForm.jsx, Dashboard.jsx
├── panels/
│   ├── ASHAPanel.jsx (New Case / My Submissions), DoctorPanel.jsx (Pending/All cases),
│   │   AdminPanel.jsx (Analytics/Users/Facilities/System)
├── components/                Shared UI: BriefingCard, TriageBadge, NavBar,
│   │                          OfflineBanner, ToastProvider, RouteGuard, UpdatePrompt
│   │                          (PWA update-available prompt), AnalyticsDashboard.
│   └── admin/                 AdminUsers, AdminFacilities, AdminStats.
public/models/
│   ├── triage_trees.json        Compact tree ensemble (~1 MB), walked in pure JS.
│   └── features_config.json     Canonical feature-order manifest.
                                 Both exported by scripts/train_classifier.py.
tests/
│   ├── treeParity.test.mjs      `npm run test:parity` — asserts the JS evaluator
│   │                            matches the server model on golden vectors (CI).
│   └── fixtures/golden_vectors.json   py-labelled vectors, written by training.
```

### Frontend build-size notes (see FEATURES_ROADMAP.md for more)

- **No onnxruntime-web at all.** Offline triage runs in pure JS
  (`treeEvaluator.js`) over `triage_trees.json`. Round 2 deleted the
  onnxruntime-web dependency and its ~12 MB WASM binary entirely — the single
  biggest weak-hardware / low-bandwidth win. The compact tree JSON (~1 MB, gzips
  far smaller) *is* now precached by the service worker (raised
  `maximumFileSizeToCacheInBytes` in `vite.config.js`), so offline triage is
  available instantly rather than being a large on-demand fetch that could fail
  exactly when connectivity drops.
- Role panels (`ASHAPanel`/`DoctorPanel`/`AdminPanel`) are `React.lazy()`-
  loaded from `App.jsx` — each user downloads only their own role's panel.
- Typical initial JS bundle ~380 KB (was ~908 KB pre-audit).

## 5. Database (Supabase)

**Important limitation of this repo**: the full database schema and Row
Level Security (RLS) policies are **not fully version-controlled**. Only
`database/phase10_realtime_setup.sql` (enables Realtime on `case_records`)
is checked in. The `profiles`, `facilities`, and `case_records` tables,
their columns, and their RLS policies exist only in the live Supabase
project. This is a known gap — see `FEATURES_ROADMAP.md` for the proposed
fix (Supabase CLI migrations, version-controlled).

**Known tables** (inferred from backend queries — not authoritative):
- `profiles` — `id` (= auth user id), `full_name`, `role`
  (`asha_worker`/`doctor`/`admin`), `facility_id`, `asha_id`, `is_active`,
  `created_at`.
- `facilities` — `id`, `name`, `type`, `address`, `district`, `state`,
  `pincode`, `phone`, `is_active`.
- `case_records` — patient/vitals/symptom fields (mirrors `IntakeForm`),
  `triage_level`, `triage_priority` (computed column: 0=EMERGENCY,
  1=URGENT, 2=ROUTINE, used for dashboard sort), `triage_confidence`,
  `risk_driver`, `briefing` (JSONB), `llm_model_used`, `client_id` (unique,
  idempotency key), `submitted_by`, `facility_id`, `reviewed_by`,
  `reviewed_at`, `created_offline`, `client_submitted_at`, `deleted_at`
  (soft delete), `created_at`.

**Role scoping model** (enforced consistently in application code — see §3's
route descriptions): `admin` = global scope (sees/manages everything). `doctor`
= scoped to their own `facility_id` when one is set (dashboard, analytics, AND —
since round 2 — the single-case detail/review endpoints, closing an IDOR).
`asha_worker` = sees only their own submissions (`submitted_by = self`, also
enforced by RLS).

## 6. Auth model

Supabase Auth issues JWTs with `user_metadata`/`app_metadata` claims including
`role` and `facility_id`. `get_current_user()` (`app/core/auth.py`) uses HYBRID
verification: it verifies the signature/exp/aud LOCALLY (HS256 via
`supabase_jwt_secret`) on the hot path — no Supabase round-trip per request —
and falls back to a network `get_user()` only when local verification can't
apply (asymmetric-key projects). It additionally re-checks `profiles.is_active`
per user on a short TTL (`revocation_recheck_seconds`, default 300s), so a
deactivated user is cut off within that window rather than working until token
expiry (~1h) — the backend previously never checked is_active at all.
`require_role(*roles)` is a dependency factory checking the decoded role against
an allow-list, 403 otherwise. Rate-limit keys use the *verified* sub
(`verify_sub_for_rate_limit`), so a forged token can't burn a victim's budget.

## 7. What NOT to change without strong reason

- `scikit-learn==1.9.0` / `shap==0.51.0` exact pins in `requirements.txt` —
  bumping requires retraining and committing new model artifacts in the
  same change (see `backend/app/ml/README.md`).
- `briefing["triage_level"] = triage_result["triage_level"]` in
  `llm.py::_enforce_schema` — the life-safety guarantee that no LLM output
  can override the ML classifier's triage decision.
- The three deterministic layers in `classifier.py` — `_safety_net_check`
  (→ EMERGENCY) and the `_news2_concerning_vital` floor (→ never ROUTINE) — and
  their exact JS mirrors in `clinicalRules.js`. Independent backstops against ML
  error on unambiguous/concerning cases; don't remove to "simplify."
- `require_role('admin')` on every `/api/admin` route — the ONLY access-control
  boundary on the RLS-bypassing service-role client (test_admin_authz enforces).
- `client_id` as the upsert idempotency key in `cases.py::submit_case` —
  what makes offline-queue retry-safe without creating duplicate cases.
- The backend `.pkl`, the frontend `triage_trees.json`, `features_config.json`,
  and `golden_vectors.json` must always be regenerated together from the same
  `train_classifier.py` run — never independently. The `npm run test:parity` CI
  check fails if the JS offline path desyncs from the server model.

## 8. Keeping this document current

When you make a change that would make a future reader's mental model of
this document wrong — a new top-level directory, a route file split or
merged, a data flow changed, a "what not to change" invariant altered —
**update the relevant section of this file in the same commit**. Small
day-to-day code changes (a new field on a form, a UI tweak, a bug fix that
doesn't change architecture) do not need a CODEBASE_MAP update. When in
doubt: if a new contributor reading only this file would be misled about
where something lives or how it flows, update it.
