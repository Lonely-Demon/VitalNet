# VitalNet 🩺

VitalNet is an offline-first clinical triage and briefing platform for rural
health workers (ASHAs) and PHC doctors in India. A local machine-learning
classifier triages patients into EMERGENCY / URGENT / ROUTINE instantly —
online or fully offline — and an LLM generates a structured clinical
briefing (differential diagnoses, red flags, recommended actions) for the
reviewing doctor. The ML triage level is never overridable by the LLM.

## 📚 Documentation map

This README gets you running locally. Everything else lives in dedicated
docs — start with whichever matches what you're trying to do:

| Doc | Read this for |
|---|---|
| **[CODEBASE_MAP.md](./CODEBASE_MAP.md)** | Every directory, what it does, architecture/sequence/ER diagrams — the primary orientation doc |
| **[docs/API_REFERENCE.md](./docs/API_REFERENCE.md)** | Every HTTP endpoint: auth, rate limits, request/response shapes |
| **[docs/DECISIONS.md](./docs/DECISIONS.md)** | *Why* the system is built this way — rejected alternatives, tradeoffs |
| **[FEATURES_ROADMAP.md](./FEATURES_ROADMAP.md)** | Proposed features with implementation-ready specs |
| **[CONTRIBUTING.md](./CONTRIBUTING.md)** | Branch strategy, PR process, commit conventions |
| **[docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md)** | What's tested, how, and how to add a test |
| **[docs/SECURITY.md](./docs/SECURITY.md)** | Security model, threat summary, how to report a vulnerability |
| **[docs/ONBOARDING.md](./docs/ONBOARDING.md)** | New-developer first-day checklist |
| **[docs/GLOSSARY.md](./docs/GLOSSARY.md)** | Domain terms (ASHA, PHC, NEWS2, triage tiers, etc.) |
| **[docs/DISASTER_RECOVERY.md](./docs/DISASTER_RECOVERY.md)** | RTO/RPO targets, restore procedures |
| **[docs/CLINICAL_GOVERNANCE.md](./docs/CLINICAL_GOVERNANCE.md)** | Regulatory posture (CDSCO), model lifecycle governance, guardrail architecture |
| **[docs/COMPLIANCE_DPDP.md](./docs/COMPLIANCE_DPDP.md)** | India DPDP Act 2023 mapping — data-principal rights, fiduciary obligations, gaps |
| **[backend/app/ml/README.md](./backend/app/ml/README.md)** + **[MODEL_CARD.md](./backend/app/ml/MODEL_CARD.md)** | ML architecture, clinical grounding, intended use/limitations |
| **[CHANGELOG.md](./CHANGELOG.md)** | Version history |
| **[AGENTS.md](./AGENTS.md)** | Conventions specifically for AI coding agents working in this repo |

---

## 🚀 Features

- **Local + Offline ML Triage**: A single `HistGradientBoostingClassifier`
  (trained on 45 engineered clinical features) predicts urgency
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
- **Role-based access**: Three roles — `asha_worker`, `doctor`, `admin` —
  enforced both via backend `require_role()` dependencies and Supabase Row
  Level Security. An Admin panel manages users (including CSV bulk
  onboarding), facilities, system stats, and the PHI audit log.
- **Production hardening**: per-user API rate limiting (`slowapi`),
  structured JSON logging, Pydantic-validated/bounded request schemas,
  prompt-injection-resistant LLM context building, a global exception
  handler that never leaks tracebacks, and a hybrid local/network JWT
  verification model that removes Supabase Auth as a single point of
  failure on the hot path (`docs/DECISIONS.md` §1).

---

## 🏗️ Architecture at a glance

```
frontend/   React 19 + Vite + Tailwind v4 PWA (offline-first, role-based panels)
backend/    FastAPI (Python) — app/api (routes), app/core (config/auth/db),
            app/ml (classifier + feature engineering), app/services (LLM, push, SMS scaffold)
```

Supabase (PostgreSQL + Auth + Realtime) is the only datastore — schema is
version-controlled in `backend/supabase/migrations/`. See
[CODEBASE_MAP.md](./CODEBASE_MAP.md) for the full file-by-file map and
architecture/sequence/entity-relationship diagrams.

---

## 🛠️ Local Development Setup

For a fully-narrated first-time walkthrough (including making a trivial
change and opening your first PR), see **[docs/ONBOARDING.md](./docs/ONBOARDING.md)**.
The condensed version:

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
cd frontend
npm install
```

Create `frontend/.env.local` (see `frontend/.env.example`):
```env
VITE_SUPABASE_URL=https://your-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key_here
VITE_API_BASE_URL=http://localhost:8000
VITE_VAPID_PUBLIC_KEY=                      # optional — omit to disable Web Push client-side
```

Run the dev server:
```bash
npm run dev
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
regenerate it if you change `app/ml/clinical_features.py` or
`scripts/train_classifier.py`:
```bash
cd backend
pip install -r requirements-train.txt
python scripts/train_classifier.py
```
This is the single source of truth for the backend `.pkl`, the frontend
`triage_trees.json`/`features_config.json`, and the tree-level golden-vector
fixture — never hand-edit any of them. See `backend/app/ml/README.md` for
the full architecture and clinical grounding, `backend/CLASSIFIER_CHANGELOG.md`
for version history, and `docs/DECISIONS.md` §12 if you touch anything
time-of-day/seasonally dependent in the feature engineering.

---

## 🧪 Testing

See **[docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md)** for the full
philosophy and coverage map. Quick reference:

```bash
# Backend — pytest suite (safety properties, admin authz, ML parity, bulk-import
# isolation, SMS parser) — offline, no server/DB required, runs in CI
cd backend && pytest tests/ --ignore=tests/test_e2e.py -v

# Backend — classifier-only smoke test (fastest feedback loop for ML changes)
cd backend && PYTHONPATH=. python tests/test_direct.py

# Backend — full integration test (needs a running server + seeded test users)
cd backend && python tests/test_e2e.py

# Backend — lint
cd backend && ruff check .

# Frontend — online/offline ML parity (both run in CI)
cd frontend && npm run test:parity           # tree-evaluator parity
cd frontend && npm run test:feature-parity   # feature-engineering parity

# Frontend — build (catches import errors, bundle-size regressions)
cd frontend && npm run build

# Frontend — Playwright offline-flow E2E (needs a running dev server + seeded users)
cd frontend && npx playwright test tests/offline.spec.js
```

---

## 🚢 Deployment

### Railway (Backend)
- Pre-configured with `Procfile`, `railway.toml`, and `runtime.txt`.
- Set the required env vars (see §2 above) in the Railway dashboard.

### Vercel (Frontend)
- Includes `vercel.json` for SPA routing.
- Set the required `VITE_*` env vars (see §3 above) in the Vercel dashboard.

### Branching for deployment
Three long-lived branches: `main`, `dev` (active development — see
**[CONTRIBUTING.md](./CONTRIBUTING.md)**), `test` (pre-production staging).
Don't develop directly on `main` — see `docs/DECISIONS.md` §9.

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
