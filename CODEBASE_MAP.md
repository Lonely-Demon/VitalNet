# VitalNet — Codebase Map

**Purpose of this document**: a single, current, high-signal reference so a
future contributor (human or AI agent) can orient in VitalNet without
re-reading the entire codebase. If you make a structural change (new
directory, new major module, a file moves, a data flow changes), **update
this document in the same commit**. Stale maps are worse than no map —
see the "Keeping this document current" section at the bottom for the
specific rule.

Last verified against the codebase: 2026-07-03 (post security/ML audit —
see git log around this date for the full change list).

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
│   │   │                            import if required vars are missing.
│   │   ├── auth.py                  get_current_user() (validates JWT via Supabase's
│   │   │                            get_user() — network call, supports instant
│   │   │                            revocation + ES256) and require_role(*roles)
│   │   │                            dependency factory.
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
│   │   ├── README.md                 Full ML architecture + clinical grounding — READ
│   │   │                             THIS before touching classifier.py or
│   │   │                             clinical_features.py.
│   │   ├── classifier.py             Public ML API: load_classifier(), predict_triage()
│   │   │                             / run_triage(), get_classifier_info(). Loads
│   │   │                             app/ml/models/triage_classifier.pkl. Runs the
│   │   │                             deterministic safety-net check BEFORE the trained
│   │   │                             model — see _safety_net_check().
│   │   ├── clinical_features.py     ClinicalFeatureEngineer — expands ~14 raw intake
│   │   │                             fields into 45 engineered features. MIRRORED in
│   │   │                             JS at frontend/src/utils/triageClassifier.js —
│   │   │                             if you change this file, port the change to JS
│   │   │                             too and retrain (see below).
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
│   └── train_classifier.py          THE training entrypoint (single unified model —
│                                     see app/ml/README.md). Outputs
│                                     app/ml/models/triage_classifier.pkl AND
│                                     frontend/public/models/{triage_classifier.onnx,
│                                     features_config.json} from one run.
├── prompts/clinical_system_prompt.txt
│                                     System prompt for the LLM briefing generator.
├── tests/
│   ├── test_direct.py                Classifier-only tests, no server/DB required —
│   │                                 fastest feedback loop for ML changes.
│   └── test_e2e.py                   Full integration test against a running server +
│                                     real Supabase auth (needs seeded test users, see
│                                     Context/test_credentials.md).
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
│   ├── useLocalTriage.js      Wires up ONNX warmup (triggered on offline/unreachable
│                              events) and classify().
│   ├── useDraftSave.js        Auto-saves IntakeForm state to IndexedDB keyed by
│                              client_id (survives tab eviction on low-RAM devices).
│   └── useRealtimeCases.js    Supabase Realtime subscription wrapper (INSERT/UPDATE),
│                              used by Dashboard, ASHAPanel history, AnalyticsDashboard.
├── utils/
│   ├── triageClassifier.js    Offline ONNX inference. buildFeatureMap() MIRRORS
│   │                          backend/app/ml/clinical_features.py — keep them in sync.
│   │                          Feature ORDER is fetched dynamically from
│   │                          /models/features_config.json at load time (not
│   │                          hard-coded) so a backend feature-set change can't
│   │                          silently desync this file. onnxruntime-web is imported
│   │                          dynamically (not at module top level) and from the
│   │                          '/wasm' subpath (not the default WebGPU-inclusive
│   │                          entry) to keep the initial bundle small — see the
│   │                          comments at the top of the file for the size rationale.
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
│   ├── triage_classifier.onnx   Exported by scripts/train_classifier.py
│   └── features_config.json     Canonical feature-order manifest, ditto
```

### Frontend build-size notes (see FEATURES_ROADMAP.md for more)

- `onnxruntime-web/wasm` subpath (WASM-only, no WebGPU/JSEP) instead of the
  default `onnxruntime-web` entry: ~12 MB WASM instead of ~25 MB.
- The onnxruntime-web JS glue is dynamically `import()`-ed inside
  `loadModel()`, not statically imported — it's excluded from the main
  bundle for users who never trigger offline/local inference.
- Role panels (`ASHAPanel`/`DoctorPanel`/`AdminPanel`) are `React.lazy()`-
  loaded from `App.jsx` — each user downloads only their own role's panel.
- The PWA service worker still *precaches* the ONNX model + WASM runtime on
  first visit (via `workbox` `globPatterns` in `vite.config.js`) regardless
  of role, because an offline-first app cannot fetch a 12 MB model for the
  first time exactly when connectivity is lost — this is a deliberate
  tradeoff, not an oversight.

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

**Role scoping model** (this IS enforced consistently in application code
as of this audit — see §3's route descriptions): `admin` = global scope
(sees/manages everything). `doctor` = scoped to their own `facility_id`
when one is set (dashboard, analytics). `asha_worker` = sees only their own
submissions (`submitted_by = self`, also enforced by RLS).

## 6. Auth model

Supabase Auth issues JWTs with `user_metadata`/`app_metadata` claims
including `role` and `facility_id`. Backend validates every request via
`get_current_user()` (`app/core/auth.py`), which calls Supabase's
`auth.get_user(token)` — a network round-trip, but it gets you instant
token revocation and ES256 signature support for free, which local-only JWT
verification would not provide. This is a deliberate latency-for-correctness
tradeoff; see `FEATURES_ROADMAP.md` if you want to explore a cached/hybrid
approach. `require_role(*roles)` is a FastAPI dependency factory checking
the decoded role against an allow-list, returning 403 otherwise.

## 7. What NOT to change without strong reason

- `scikit-learn==1.9.0` / `shap==0.51.0` exact pins in `requirements.txt` —
  bumping requires retraining and committing new model artifacts in the
  same change (see `backend/app/ml/README.md`).
- `briefing["triage_level"] = triage_result["triage_level"]` in
  `llm.py::_enforce_schema` — the life-safety guarantee that no LLM output
  can override the ML classifier's triage decision.
- The safety-net override in `classifier.py::_safety_net_check` — a
  deterministic backstop independent of the trained model; don't remove it
  to "simplify," it's the guarantee against ML error on unambiguous cases.
- `client_id` as the upsert idempotency key in `cases.py::submit_case` —
  what makes offline-queue retry-safe without creating duplicate cases.
- The backend `.pkl` and frontend `.onnx` must always be regenerated
  together from the same `train_classifier.py` run — never independently.

## 8. Keeping this document current

When you make a change that would make a future reader's mental model of
this document wrong — a new top-level directory, a route file split or
merged, a data flow changed, a "what not to change" invariant altered —
**update the relevant section of this file in the same commit**. Small
day-to-day code changes (a new field on a form, a UI tweak, a bug fix that
doesn't change architecture) do not need a CODEBASE_MAP update. When in
doubt: if a new contributor reading only this file would be misled about
where something lives or how it flows, update it.
