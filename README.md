# VitalNet 🩺

VitalNet is an offline-first clinical triage and briefing platform for rural
health workers (ASHAs) and PHC doctors in India. A local machine-learning
classifier triages patients into EMERGENCY / URGENT / ROUTINE instantly —
online or fully offline — wrapped by a deterministic safety net and NEWS2
floor that force-escalate unambiguous critical presentations independent of
the model, and an LLM generates a structured clinical briefing (differential
diagnoses, red flags, recommended actions) for the reviewing doctor. The
triage level is never overridable by the LLM.

> **Mid-migration:** this repo is partway through a TypeScript rebuild
> (`docs/DECISIONS.md` §33). `packages/clinical-core` now holds a
> re-architected version of this logic — a deterministic rules engine
> that's *authoritative* (the model becomes advisory-only, prioritization
> signal) — running in a new Supabase Edge Function backend (`apps/api`).
> **`apps/api` has not received production traffic yet.** Every endpoint is
> still served by the legacy FastAPI backend (`backend/app/`) with the
> model-primary design described above, and that's what the rest of this
> README documents unless stated otherwise. See "Architecture at a glance"
> below.

## 📚 Documentation map

This README gets you running locally. Everything else lives in dedicated
docs — start with whichever matches what you're trying to do:

| Doc | Read this for |
|---|---|
| **[CODEBASE_MAP.md](./CODEBASE_MAP.md)** | Every directory, what it does, architecture/sequence/ER diagrams — the primary orientation doc |
| **[docs/API_REFERENCE.md](./docs/API_REFERENCE.md)** | Every HTTP endpoint: auth, rate limits, request/response shapes |
| **[docs/DECISIONS.md](./docs/DECISIONS.md)** | *Why* the system is built this way — rejected alternatives, tradeoffs |
| **[docs/LESSONS_LEARNED.md](./docs/LESSONS_LEARNED.md)** | Living notes for future agents: verification methodology, dead ends, and — importantly — substantive unmerged work sitting on stale branches |
| **[docs/RESEARCH_AND_DEVELOPMENT.md](./docs/RESEARCH_AND_DEVELOPMENT.md)** | The full R&D record — problem research, competitive landscape, AI-layer design rationale, feasibility, impact |
| **[FEATURES_ROADMAP.md](./FEATURES_ROADMAP.md)** | Proposed features with implementation-ready specs |
| **[CONTRIBUTING.md](./CONTRIBUTING.md)** | Branch strategy, PR process, commit conventions |
| **[docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md)** | What's tested, how, and how to add a test |
| **[docs/SECURITY.md](./docs/SECURITY.md)** | Security model, threat summary, how to report a vulnerability |
| **[docs/ONBOARDING.md](./docs/ONBOARDING.md)** | New-developer first-day checklist |
| **[docs/GLOSSARY.md](./docs/GLOSSARY.md)** | Domain terms (ASHA, PHC, NEWS2, triage tiers, etc.) |
| **[docs/DISASTER_RECOVERY.md](./docs/DISASTER_RECOVERY.md)** | RTO/RPO targets, restore procedures |
| **[docs/INCIDENT_RESPONSE.md](./docs/INCIDENT_RESPONSE.md)** | Security incident runbook — detection through post-incident review |
| **[docs/CLINICAL_GOVERNANCE.md](./docs/CLINICAL_GOVERNANCE.md)** | Regulatory posture (CDSCO), model lifecycle governance, guardrail architecture |
| **[docs/CLINICAL_REVIEW.md](./docs/CLINICAL_REVIEW.md)** | Sign-off checklist for changes to the clinical rules engine; the rules-first cutover's outstanding gate |
| **[docs/COMPLIANCE_DPDP.md](./docs/COMPLIANCE_DPDP.md)** | India DPDP Act 2023 mapping — data-principal rights, fiduciary obligations, gaps |
| **[docs/ACCESSIBILITY.md](./docs/ACCESSIBILITY.md)** | WCAG 2.1 AA audit — what's fixed, what's verified, what's an honest known gap |
| **[docs/SLO.md](./docs/SLO.md)** | Service level objectives, SLIs, and the `/api/metrics` Prometheus endpoint |
| **[backend/app/ml/README.md](./backend/app/ml/README.md)** + **[MODEL_CARD.md](./backend/app/ml/MODEL_CARD.md)** | ML architecture, clinical grounding, intended use/limitations (legacy backend; still accurate for what's live today) |
| **[packages/clinical-core/README.md](./packages/clinical-core/README.md)** | The single source of clinical truth (TypeScript) — rules engine, features, offline tree evaluator |
| **[apps/api/README.md](./apps/api/README.md)** | The new Supabase Edge Function backend — not yet receiving production traffic |
| **[apps/web/README.md](./apps/web/README.md)** | The frontend PWA — layout, offline outbox, local dev |
| **[CHANGELOG.md](./CHANGELOG.md)** | Version history |
| **[AGENTS.md](./AGENTS.md)** | Conventions specifically for AI coding agents working in this repo |

---

## 🚀 Features

- **Local + Offline ML Triage**: A single `HistGradientBoostingClassifier`
  (trained on 43 engineered clinical features) predicts urgency
  (EMERGENCY/URGENT/ROUTINE). It runs server-side (Python) for online
  submissions and client-side for offline submissions — as a compact tree
  JSON walked by a **dependency-free pure-JS evaluator** (no onnxruntime/WASM),
  which keeps the offline model ~1 MB instead of a ~12 MB WASM runtime, so it
  runs comfortably on 2 GB-class devices over metered rural links. The **same
  trained model** runs in both places (golden-vector parity test enforced), so
  online and offline triage never disagree. See `docs/DECISIONS.md` §§2-3 for
  the full rationale.
- **Deterministic safety-net escalation**: Independent of the trained
  model's own prediction, an explicit rule set force-escalates unambiguous
  critical presentations (e.g. SpO2 < 85%, extreme vitals, altered
  consciousness, hypertensive crisis with neurological symptoms) to
  EMERGENCY, plus a NEWS2-based floor that never lets a single concerning
  vital resolve to ROUTINE. See `backend/app/ml/README.md`.
- **Real SHAP Risk Explanations**: Every prediction (outside the safety-net
  path) is explained using actual `shap.TreeExplainer` feature attributions
  for the model's own decision, translated into clinical language.
- **AI Clinical Briefings**: A 4-tier LLM fallback chain (Groq Llama-3.3-70B
  → Llama-3.1-8B → Gemini 2.5 Flash → Gemini 2.5 Flash-Lite) generates
  differential diagnoses, red flags, and recommended actions. The triage
  level and disclaimer are hard-locked post-generation — no LLM output can
  change them.
- **Offline-first PWA**: ASHA workers can fill out and submit intake forms
  with no connectivity. Submissions queue in IndexedDB, drafts auto-save
  (survives tab eviction on low-RAM Android tablets), and a background sync
  drains the queue when connectivity returns.
- **Priority Doctor Dashboard**: Real-time (Supabase Realtime) case feed,
  sorted EMERGENCY → URGENT → ROUTINE then by recency, with correct
  composite-keyset cursor pagination. Doctors can override the ML triage
  (with a required reason — feeds the retraining loop), record patient
  outcomes, and refer cases to other facilities.
- **Web Push + escalation**: Doctors optionally subscribe to push
  notifications for new EMERGENCY cases; an admin-triggered (externally
  scheduled) endpoint re-escalates any EMERGENCY case still unreviewed past
  15 minutes.
- **Analytics & reporting**: Response-time SLA dashboard, ML/doctor
  agreement rate, and a CSV export for facility reporting.
- **Multi-language intake (infrastructure)**: `react-i18next` is fully
  wired with a persisted language switcher — Hindi/Tamil translations are
  intentionally left as reviewed-pending English placeholders (see
  `docs/DECISIONS.md` §10, a patient-safety decision, not an oversight).
- **Voice-to-text intake assist**: Browser-native speech-to-text on
  free-text fields, gated on connectivity (Chrome's engine needs it).
- **Role-based access**: Four roles — `asha_worker`, `doctor`, `supervisor`,
  `admin` — enforced both via backend `require_role()` dependencies and
  Supabase Row Level Security. `supervisor` (modeled on NHM's real ASHA
  Facilitator role) gets a facility-scoped, aggregate-only, non-PHI team
  dashboard — see `docs/DECISIONS.md` §25. An Admin panel manages users
  (including CSV bulk onboarding), facilities, system stats, and the PHI
  audit log.
- **Outbreak signals**: a lightweight EARS C1 aberration-detection
  dashboard over facility symptom counts — informational only, not a
  validated surveillance system (`docs/DECISIONS.md` §26).
- **Protocol assistant**: a grounded guideline lookup tool (ANC schedule,
  immunisation schedule, danger signs, referral criteria) informed by
  ASHABot's own published design, with async human curation instead of its
  too-slow synchronous consensus (`docs/DECISIONS.md` §27).
- **Production hardening**: per-user API rate limiting (`slowapi`),
  structured JSON logging, Pydantic-validated/bounded request schemas,
  prompt-injection-resistant LLM context building, a global exception
  handler that never leaks tracebacks, and a hybrid local/network JWT
  verification model that removes Supabase Auth as a single point of
  failure on the hot path (`docs/DECISIONS.md` §1).

---

## 🏗️ Architecture at a glance

A pnpm workspace monorepo, mid strangler-fig migration:

```
packages/clinical-core/   THE single source of clinical truth (TypeScript): Zod intake
                           schema, deterministic rules engine (bands/overrides/citations),
                           43-feature engineering, offline tree evaluator + Saabas
                           attribution, contraindications. Consumed by both apps/web
                           (offline, in the browser) and apps/api (online) — one
                           implementation, not two kept in sync by hand.
apps/web/                 React 19 + Vite + Tailwind v4 PWA (offline-first, role-based
                           panels). Imports @vitalnet/clinical-core directly.
apps/api/                 NEW backend: one Supabase Edge Function (Deno + Hono) running
                           clinical-core in rules-first mode. NOT YET LIVE — every
                           endpoint in apps/web's ENDPOINT_BACKEND map still resolves
                           to 'legacy' below.
backend/                  LIVE (legacy) backend: FastAPI (Python) — app/api (routes),
                           app/core (config/auth/db), app/ml (classifier + feature
                           engineering, model-primary + safety net), app/services (LLM,
                           push, SMS scaffold). Deployable and serving all production
                           traffic until apps/api is cut over.
tools/training/            Python ML training pipeline (train_classifier.py and friends).
                           Labels and features come from packages/clinical-core via a
                           JSONL subprocess (cli.mjs) — Python only does sklearn
                           training + ONNX→tree-JSON export now.
```

Supabase (PostgreSQL + Auth + Realtime) is the only datastore — schema is
version-controlled in `backend/supabase/migrations/`, shared by both
backends. See [CODEBASE_MAP.md](./CODEBASE_MAP.md) for the full
file-by-file map and architecture/sequence/entity-relationship diagrams,
and each subdirectory's own README for that piece's specifics.

---

## 🛠️ Local Development Setup

**Quick start:** `./setup.sh` installs both the backend and frontend
dependencies and walks you through creating `backend/.env.local` and
`apps/web/.env.local` from the `.env.example` templates (prompting once for
each key — anything left blank stays as the template placeholder and can be
filled in later). Both `.env.local` files are gitignored; nothing this
script writes is ever committed, and it's safe to re-run — it never
overwrites an `.env.local` that already has real values. It still can't
create a Supabase project for you or run its migrations — see step 1 below
for what's left. It sets up the legacy FastAPI backend + the frontend — the
pair that actually serves production traffic today (see the migration note
above). `apps/api` (the new edge function) is a separate, optional local
setup — see `apps/api/README.md`.

For a fully-narrated first-time walkthrough (including making a trivial
change and opening your first PR), see **[docs/ONBOARDING.md](./docs/ONBOARDING.md)**.
The manual, step-by-step version `setup.sh` automates:

### 1. Prerequisites
- **Python 3.13** (production target — see `backend/runtime.txt`; 3.11+
  also works for local development)
- **Node.js** (v20+ recommended)
- **A Supabase project** (PostgreSQL + Auth + Realtime) — VitalNet has no
  other database backend. Run every migration in
  `backend/supabase/migrations/` **in numeric order** against your
  Supabase project's SQL editor (or via the Supabase CLI).
- **Groq API Key** (required — primary LLM tier)
- **Gemini API Key** (optional — tiers 3/4 fallback; app starts and runs
  fine without it, briefings just have fewer fallback tiers)

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env.local` (see `backend/.env.example` for the full list
with explanations — this is the abbreviated required set):
```env
SUPABASE_URL=https://your-ref.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
GROQ_API_KEY=your_groq_api_key_here
CSRF_TOKEN=vitalnet-spa                    # must match the frontend's value
```
Optional but worth knowing about (all documented in `backend/.env.example`):
`GEMINI_API_KEY`, `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS`, `ENVIRONMENT`,
`API_DOCS_ENABLED`, `RATE_LIMIT_STORAGE_URI` (Redis for multi-instance
deployments), `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/`VAPID_SUBJECT` (Web
Push — omit to disable push notifications entirely, Realtime still works),
`DATA_RETENTION_DAYS` (DPDP retention sweep, `docs/COMPLIANCE_DPDP.md` —
0 disables it).

Run the server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```
The API is available at http://localhost:8000 — check
http://localhost:8000/api/health to verify the database connection and ML
classifier both loaded successfully.

### 3. Frontend Setup
```bash
pnpm install --filter @vitalnet/web...   # from the repo root — pnpm workspace
```

Create `apps/web/.env.local` (see `apps/web/.env.example`):
```env
VITE_SUPABASE_URL=https://your-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key_here
VITE_API_BASE_URL=http://localhost:8000
VITE_VAPID_PUBLIC_KEY=                      # optional — omit to disable Web Push client-side
```

Run the dev server:
```bash
pnpm --filter @vitalnet/web dev
```
The app is available at http://localhost:5173.

### 4. Seed test users (optional)
See `Context/test_credentials.md` for the standard test accounts
(`asha@test.vitalnet` / `doctor@test.vitalnet` / `admin@test.vitalnet`).
`backend/seed_user.py` is a one-off script to create/fix a test doctor
account directly via the Supabase admin client — read the warning banner
at the top of the file before running it.

### 5. Regenerating the ML classifier
The classifier is trained and committed, not built at deploy time. Only
regenerate it if you change `app/ml/clinical_features.py`,
`packages/clinical-core/src/rules/` or `features.ts`:
```bash
pnpm --filter @vitalnet/clinical-core build
cd tools/training
pip install -r ../../backend/requirements-train.txt
python train_classifier.py
```
This is the single source of truth for the backend `.pkl`, the frontend
`triage_trees.json`/`features_config.json`, and the golden-vector
fixtures — never hand-edit any of them. Labels and features both come from
`packages/clinical-core` via a subprocess CLI, so there's no longer a
separate Python scoring function to keep in sync. See
`backend/app/ml/README.md` for the full architecture and clinical
grounding, `backend/CLASSIFIER_CHANGELOG.md` for version history, and
`docs/DECISIONS.md` §23 if you touch anything time-of-day/seasonally
dependent in the feature engineering.

---

## 🧪 Testing

See **[docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md)** for the full
philosophy and coverage map. Quick reference:

```bash
# Backend (legacy, live) — pytest suite (safety properties, admin authz, ML
# parity, bulk-import isolation, SMS parser) — offline, no server/DB
# required, runs in CI
cd backend && pytest tests/ --ignore=tests/test_e2e.py -v

# Backend — classifier-only smoke test (fastest feedback loop for ML changes)
cd backend && PYTHONPATH=. python tests/test_direct.py

# Backend — full integration test (needs a running server + seeded test users)
cd backend && python tests/test_e2e.py

# Backend — lint
cd backend && ruff check .

# clinical-core — the authoritative rules-engine/feature-engineering suite:
# embedded per-rule vectors, safety/fuzz suites, golden vectors (this is
# what the old frontend-side parity suites were replaced by, see apps/web/README.md)
pnpm --filter @vitalnet/clinical-core test

# apps/api (new backend, not yet live) — Deno test suite
cd apps/api/supabase/functions/api && deno test --allow-net --allow-env

# apps/web — build (catches import errors, bundle-size regressions)
pnpm --filter @vitalnet/web run build

# apps/web — Playwright offline-flow E2E (needs a running dev server + seeded users)
cd apps/web && npx playwright test tests/offline.spec.js
```

---

## 🚢 Deployment

### Railway (Backend — legacy, live)
- Pre-configured with `Procfile`, `railway.toml`, and `runtime.txt`.
- Set the required env vars (see §2 above) in the Railway dashboard.

### Vercel (Frontend)
- `apps/web/vercel.json` for SPA routing.
- Set the required `VITE_*` env vars (see §3 above) in the Vercel dashboard.

### Supabase Edge Functions (apps/api — new backend, not yet live)
- `supabase functions deploy api` from `apps/api/`, after `pnpm --filter
  @vitalnet/clinical-core build` (bundles the relative dist/ dependency —
  see `apps/api/README.md`).
- CI has a manual (`workflow_dispatch`-only) deploy job:
  `.github/workflows/api-edge-function.yml`'s `deploy` job. It does not fire
  on push/PR — deploying is a deliberate action, gated on the
  `SUPABASE_ACCESS_TOKEN`/`SUPABASE_PROJECT_REF` repo secrets being set.
  Deploying does not, by itself, send it any production traffic — that's a
  separate step (flipping an entry in `apps/web/src/api/base.js`'s
  `ENDPOINT_BACKEND` map).

### Branching for deployment
Three long-lived branches: `main`, `dev` (active development — see
**[CONTRIBUTING.md](./CONTRIBUTING.md)**), `test` (pre-production staging).
Don't develop directly on `main` — see `docs/DECISIONS.md` §9.

### Free-tier keep-alive jobs
Running on free tiers end to end has two failure modes this repo works
around (`docs/DECISIONS.md` §28):
- **Supabase pauses a project after 7 days of no database activity.**
  `.github/workflows/supabase-keepalive.yml` pings it every ~3 days. Set
  repo secrets `SUPABASE_URL` and `SUPABASE_ANON_KEY` (Settings > Secrets
  and variables > Actions > Secrets) to enable it.
- **Free backend hosts (Render, etc.) spin down after ~10-15 min idle**,
  causing a cold-start on the next request. `.github/workflows/
  backend-keepalive.yml` pings `GET /api/health` every 10 minutes. Set repo
  variable `BACKEND_HEALTH_URL` (same Settings page, Variables tab) to your
  deployed backend's base URL once you have one. Read the workflow's own
  comments before relying on it — GitHub's schedule trigger has documented,
  sometimes-large delays, so a dedicated uptime monitor (UptimeRobot,
  cron-job.org, etc.) is the more reliable fix if cold-starts are a real
  problem in practice.

---

## 🔒 Security

See **[docs/SECURITY.md](./docs/SECURITY.md)** for the full security model
and how to report a vulnerability. Key points for anyone extending the API:
- All request payloads are Pydantic-validated with explicit bounds
  (`backend/app/models/schemas.py`) — add bounds to any new field.
- All authenticated routes go through `require_role()` — never trust a
  role claim without it.
- All routes are rate-limited via the shared `slowapi` `Limiter` in
  `app/api/routes/cases.py`, keyed on the *verified* JWT `sub`.
- Free-text fields reaching the LLM prompt are sanitised
  (`app/services/llm.py::_sanitize_field`) — never interpolate raw
  user input into a prompt without it.
- RLS policies are version-controlled in `backend/supabase/migrations/`
  and must be re-applied to the live Supabase project's SQL editor when
  they change.

---

## 📝 License
This project began as a rapid development sprint and has since gone
through multiple hardening phases (see `docs/ARCHITECTURE_RESTRUCTURE.md`,
`docs/REBUILD_INSTRUCTIONS.md`, `docs/IMPROVEMENTS.md` for that history).
Built with 🩺 by Antigravity.
