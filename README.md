# VitalNet 🩺

VitalNet is an offline-first clinical triage and briefing platform for rural
health workers (ASHAs) and PHC doctors in India. A local machine-learning
classifier triages patients into EMERGENCY / URGENT / ROUTINE instantly —
online or fully offline — and an LLM generates a structured clinical
briefing (differential diagnoses, red flags, recommended actions) for the
reviewing doctor. The ML triage level is never overridable by the LLM.

For a full map of the codebase (every directory, what it does, and where to
look for a given kind of change), see **[CODEBASE_MAP.md](./CODEBASE_MAP.md)**.
For the proposed feature roadmap with implementation-ready specs, see
**[FEATURES_ROADMAP.md](./FEATURES_ROADMAP.md)**.

## 🚀 Features

- **Local + Offline ML Triage**: A single `HistGradientBoostingClassifier`
  (trained on 45 engineered clinical features) predicts urgency
  (EMERGENCY/URGENT/ROUTINE). It runs server-side (Python) for online
  submissions and client-side (ONNX via `onnxruntime-web`, WASM) for offline
  submissions — the **same trained model** in both places, so online and
  offline triage never disagree.
- **Deterministic safety-net escalation**: Independent of the trained
  model's own prediction, an explicit rule set force-escalates unambiguous
  critical presentations (e.g. SpO2 < 85%, extreme vitals, altered
  consciousness, hypertensive crisis with neurological symptoms) to
  EMERGENCY. See `backend/app/ml/README.md` for the full clinical rationale.
- **Real SHAP Risk Explanations**: Every prediction (outside the safety-net
  path) is explained using actual `shap.TreeExplainer` feature attributions
  for the model's own decision, translated into clinical language — not a
  hand-written heuristic guessing what mattered.
- **AI Clinical Briefings**: A 4-tier LLM fallback chain (Groq Llama-3.3-70B
  → Llama-3.1-8B → Gemini 2.5 Flash → Gemini 2.5 Flash-Lite) generates
  differential diagnoses, red flags, and recommended actions. The triage
  level and disclaimer are hard-locked post-generation — no LLM output can
  change them.
- **Offline-first PWA**: ASHA workers can fill out and submit intake forms
  with no connectivity. Submissions queue in IndexedDB, drafts auto-save
  (survives tab eviction on low-RAM Android tablets), and a background sync
  drains the queue when connectivity returns — paced to stay under the API
  rate limit.
- **Priority Doctor Dashboard**: Real-time (Supabase Realtime) case feed,
  sorted EMERGENCY → URGENT → ROUTINE then by recency, with correct
  composite-keyset cursor pagination (no silent data loss at tier
  boundaries).
- **Role-based access**: Three roles — `asha_worker`, `doctor`, `admin` —
  enforced both via backend `require_role()` dependencies and Supabase Row
  Level Security. An Admin panel manages users, facilities, and system
  stats.
- **Production hardening**: per-user API rate limiting (`slowapi`),
  structured JSON logging, Pydantic-validated/bounded request schemas,
  prompt-injection-resistant LLM context building, and a global exception
  handler that never leaks tracebacks to clients.

---

## 🏗️ Architecture at a glance

```
frontend/   React 19 + Vite + Tailwind v4 PWA (offline-first, role-based panels)
backend/    FastAPI (Python) — app/api (routes), app/core (config/auth/db),
            app/ml (classifier + feature engineering), app/services (LLM)
database/   Supabase (PostgreSQL) SQL setup scripts (RLS/Realtime — the
            authoritative RLS policies live in the Supabase project itself,
            not fully version-controlled here — see CODEBASE_MAP.md)
```

See [CODEBASE_MAP.md](./CODEBASE_MAP.md) for the full file-by-file map.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- **Python 3.13** (production target — see `backend/runtime.txt`; 3.11+
  also works for local development)
- **Node.js** (v20+ recommended)
- **A Supabase project** (PostgreSQL + Auth + Realtime) — VitalNet has no
  other database backend. Create tables `profiles`, `facilities`,
  `case_records` per your Supabase project setup, and run
  `database/phase10_realtime_setup.sql` to enable Realtime on `case_records`.
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

Create `backend/.env.local` (see `backend/.env.example`):
```env
SUPABASE_URL=https://your-ref.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here   # optional
FRONTEND_URL=http://localhost:5173         # optional, added to CORS allow-list
```

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
account directly via the Supabase admin client — read it before running,
it mutates your Supabase project's auth users.

### 5. Regenerating the ML classifier
The classifier is trained and committed, not built at deploy time. Only
regenerate it if you change `app/ml/clinical_features.py` or
`scripts/train_classifier.py`:
```bash
cd backend
pip install -r requirements-train.txt
python scripts/train_classifier.py
```
See `backend/app/ml/README.md` for the full architecture and clinical
grounding, and `backend/CLASSIFIER_CHANGELOG.md` for version history.

---

## 🧪 Testing

```bash
cd backend
python tests/test_direct.py    # classifier only, no server/DB needed
python tests/test_e2e.py       # full API + Supabase auth integration (needs a running server + seeded test users)
```

See `AGENTS.md` for linting, formatting, and contribution conventions.

---

## 🚢 Deployment

### Railway (Backend)
- Pre-configured with `Procfile`, `railway.toml`, and `runtime.txt`.
- Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`,
  `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, and optionally
  `GEMINI_API_KEY`/`FRONTEND_URL` in the Railway dashboard environment
  variables.

### Vercel (Frontend)
- Includes `vercel.json` for SPA routing.
- Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and
  `VITE_API_BASE_URL` (your production backend URL) in the Vercel
  dashboard.

---

## 🔒 Security

VitalNet has been through a structured Red Team audit — see the fixes
documented in `backend/CLASSIFIER_CHANGELOG.md` and commit history for
specifics. Key points for anyone extending the API:
- All request payloads are Pydantic-validated with explicit bounds
  (`backend/app/models/schemas.py`) — add bounds to any new field.
- All authenticated routes go through `require_role()` — never trust a
  role claim without it.
- All routes are rate-limited via the shared `slowapi` `Limiter` in
  `app/api/routes/cases.py` — apply `@limiter.limit(...)` to any new route.
- Free-text fields reaching the LLM prompt are sanitised
  (`app/services/llm.py::_sanitize_field`) — never interpolate raw
  user input into a prompt without it.
- RLS policies live in the Supabase project itself and are **not fully
  version-controlled in this repo** (only `database/phase10_realtime_setup.sql`
  is checked in) — this is a known gap, see `FEATURES_ROADMAP.md`.

---

## 📝 License
This project began as a 24-hour rapid development sprint and has since
gone through multiple hardening phases (see `Context/` for historical
phase documents). Built with 🩺 by Antigravity.
