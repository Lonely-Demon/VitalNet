# VitalNet Agent Instructions (AGENTS.md)

This document provides essential instructions, commands, and code style guidelines for agentic coding assistants (e.g., Claude, Cursor, Copilot, Antigravity) operating in the VitalNet repository. Always refer to these guidelines before modifying code, reading context, or running commands.

For deeper context beyond conventions: **[CODEBASE_MAP.md](./CODEBASE_MAP.md)** (architecture + diagrams), **[docs/API_REFERENCE.md](./docs/API_REFERENCE.md)** (every endpoint), **[docs/DECISIONS.md](./docs/DECISIONS.md)** (why things are built this way — read before "simplifying" anything that looks odd), **[CONTRIBUTING.md](./CONTRIBUTING.md)** (branch/PR workflow).

## 🏗️ Project Architecture Overview

**Mid-migration** (`docs/DECISIONS.md` §33) — read this before assuming which
backend a task touches:
- **`backend/`** — the LEGACY backend, Python 3.13 + FastAPI + Supabase +
  Groq/Gemini LLMs + scikit-learn. **Still serves 100% of production
  traffic.** Deployable until `apps/api` is cut over; do not delete it or
  its CI/keepalive workflow without explicit instruction.
- **`packages/clinical-core/`** — the single source of clinical truth
  (TypeScript): Zod schema, rules engine, feature engineering, offline tree
  evaluator. Used by both `apps/web` (browser) and `apps/api` (server) —
  there is no longer a hand-mirrored copy anywhere.
- **`apps/web/`** — the frontend (React 19, Vite, Tailwind v4, JS/JSX, no
  TypeScript, react-i18next, PWA). Imports `@vitalnet/clinical-core`
  directly. Talks to `backend/` (legacy, live) today — `apps/web/src/api/
  base.js`'s `ENDPOINT_BACKEND` map decides per-endpoint, and every entry is
  currently `'legacy'`.
- **`apps/api/`** — the NEW backend (Deno + Hono, one Supabase Edge
  Function), running clinical-core in rules-first mode. **Not yet live** —
  builds and tests green in CI, but receives no production traffic.
- **`tools/training/`** — the Python ML training pipeline. Generates
  synthetic patients and pipes them through `packages/clinical-core` (via a
  subprocess CLI) for labels and features; Python only does sklearn
  training + ONNX→tree-JSON export now.
- **Monorepo structure**: pnpm workspace (`pnpm-workspace.yaml`:
  `apps/*`, `packages/*`) + the standalone `backend/` (Python, not part of
  the pnpm workspace) and `tools/training/` (Python).

---

## 🌿 Git Branch Workflow — read before your first commit

Exactly three long-lived branches for building, testing, and deploying what's
already shipped: **`dev`** (active development — work here), **`main`** (periodically synced to match `dev` once verified-good), **`test`** (pre-production staging). See `docs/DECISIONS.md` §9 for the full rationale.

- **Do your work on `dev`** (or a short-lived feature branch merged into `dev` via PR). Do not develop directly on `main`.
- Both `main` and `dev` have branch protection rejecting plain merge commits via the GitHub API/UI — PRs merge via **squash or rebase only**. GitHub auto-deletes the head branch on merge.
- `pull_request`-triggered CI workflows run using the workflow file from the **base** branch, not the PR's head branch (a GitHub security feature) — a CI config change in a PR only takes effect for *future* PRs once merged into the base branch itself.
- `.github/dependabot.yml` targets `dev`.
- If `main` needs to catch up to `dev` (e.g. because Dependabot/security scanning watches the configured default branch): merge `dev` into `main` favoring `dev`'s content, push to a branch, open a PR, squash-merge — do not re-do work independently on `main`.

**Fourth branch, `experimental`, is a separate track for major reforms** —
multi-phase architectural rewrites expected to leave the repo in an
intermediate/broken state across many commits (e.g. a language migration).
It is NOT branched from and does not merge into `dev`/`main`/`test` as part
of routine work; those three stay reserved for building, testing, and
deploying already-shipped functionality. See `docs/DECISIONS.md` §32.

---

## 🚀 Build, Run, and Lint Commands

### Backend (Python/FastAPI — legacy, live)
Always operate within a virtual environment (`python -m venv venv && source venv/bin/activate`).
- **Install Dependencies**: `pip install -r backend/requirements.txt`
- **Run Server**: `cd backend && python -m uvicorn app.main:app --reload --port 8000`
- **Linting**: `cd backend && ruff check .`
- **Formatting**: `cd backend && ruff format .`
- **Regenerate ML Models**: `pnpm --filter @vitalnet/clinical-core build && cd tools/training && pip install -r ../../backend/requirements-train.txt && python train_classifier.py`
  (regenerates `app/ml/models/triage_classifier.pkl` (backend), `apps/web/public/models/triage_trees.json` + `features_config.json` (offline, pure-JS — no ONNX runtime), and the golden-vector fixtures from ONE training run so online/offline triage can never disagree. Labels and features both come from `packages/clinical-core` via a subprocess CLI — there is no Python copy left to mirror.)

### apps/web (React/Vite — pnpm workspace)
- **Install Dependencies**: `pnpm install --filter @vitalnet/web...` (from repo root — resolves the `@vitalnet/clinical-core` workspace dependency; plain `npm install` inside `apps/web` will not)
- **Run Dev Server**: `pnpm --filter @vitalnet/web dev`
- **Build for Production**: `pnpm --filter @vitalnet/web run build`
- **Preview Build**: `pnpm --filter @vitalnet/web preview`

### packages/clinical-core (TypeScript)
- **Build**: `pnpm --filter @vitalnet/clinical-core build` (required before running apps/api or tools/training — both consume the `dist/` output, which is gitignored)
- **Test**: `pnpm --filter @vitalnet/clinical-core test`

### apps/api (Deno + Hono — new backend, not yet live)
- **Run locally**: `cd apps/api && supabase functions serve api` (after building clinical-core)
- **Test/lint/typecheck**: from `apps/api/supabase/functions/api/`: `deno test --allow-net --allow-env`, `deno lint .`, `deno check index.ts`, `deno fmt .`

---

## 🧪 Testing Guidelines

Full philosophy and coverage map: **[docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md)**. Summary:

- **Backend (legacy) pytest suite** (offline, no server/DB — runs in CI):
  ```bash
  cd backend && pytest tests/ --ignore=tests/test_e2e.py -v
  ```
  Covers: classifier safety properties (`test_classifier_safety.py`), admin-route authz (`test_admin_authz.py`), the legacy `ClinicalFeatureEngineer`'s own regression fixture (`test_feature_parity.py` — Python-internal now, not a JS parity check, see that file's header), bulk-user-import row isolation (`test_bulk_user_import.py`), SMS parser (`test_sms_parser.py`). `conftest.py` supplies fake JWT-format Supabase creds so these never need a live project.
- **Classifier-only smoke test** (fastest feedback loop for ML changes, no server/DB):
  ```bash
  cd backend && PYTHONPATH=. python tests/test_direct.py
  ```
- **Full E2E** (needs a running server + seeded Supabase test users — see `Context/test_credentials.md`):
  ```bash
  cd backend && python tests/test_e2e.py
  ```
  Not run in the unit-test CI job (needs a live server).
- **clinical-core test suite** (CI-enforced — the authoritative rules-engine/feature-engineering tests, incl. golden vectors that replaced the old frontend-side parity suites):
  ```bash
  pnpm --filter @vitalnet/clinical-core test
  ```
  The tree/feature golden fixtures freeze the clock to a fixed reference instant (`docs/DECISIONS.md` §23) — if you add a new time-dependent engineered feature, extend that freeze or these will flake.
- **apps/api test suite** (Hono `app.request()` contract tests, Deno):
  ```bash
  cd apps/api/supabase/functions/api && deno test --allow-net --allow-env
  ```
- **apps/web build**: `pnpm --filter @vitalnet/web run build` — catches import errors and lets you inspect bundle-size regressions.
- **Playwright E2E**: `cd apps/web && npx playwright test tests/offline.spec.js` — needs a running dev server + seeded users.
- **Training pipeline smoke test** (fast, CI-enforced — does NOT run a real 36k-patient training run):
  ```bash
  cd tools/training && python smoke_test.py
  ```
- **Adding New Tests**: backend tests are real `pytest` files (`tests/test_<feature>.py`) — prefer `assert`-based pytest style over the older print-driven standalone-script pattern (`test_direct.py`/`test_e2e.py` predate this and are kept as-is for their specific purposes — a fast no-DB smoke test and a full-integration script respectively — but don't add *new* tests in that style). Ensure tests do not mutate production Supabase data.

---

## 🧑‍💻 Code Style & Conventions

### 1. Python (Backend)
- **Async Framework**: FastAPI routes should heavily utilize `async def` and `await` for I/O bound operations (database calls, LLM generation).
- **Typing**: Use standard Python type hints extensively. E.g., `async def process_data(user_id: str, payload: dict) -> list:`. Pydantic models (in `schemas.py`) should be used for all request/response validation.
- **Imports**:
  1. Standard library imports
  2. Third-party library imports (`fastapi`, `pydantic`, `supabase`)
  3. Local application imports, using the full `app.*` package path (e.g. `from app.core.database import ...`, `from app.ml.classifier import ...`) — the backend is a proper `app/` package (see `docs/ARCHITECTURE_RESTRUCTURE.md`), not flat files
- **Naming**:
  - `snake_case` for variables, functions, and file names.
  - `PascalCase` for Pydantic models and classes.
  - `UPPER_SNAKE_CASE` for global constants.
- **Error Handling**:
  - Use FastAPI's `HTTPException` for expected API errors (e.g., `raise HTTPException(status_code=404, detail="Not found")`).
  - Catch specific exceptions rather than bare `except Exception:`.
  - Log errors clearly server-side; never put exception text or PII in an HTTP response body (see `docs/SECURITY.md`).
- **New route checklist**: bounded Pydantic request model → `require_role(...)` dependency → `@limiter.limit(...)` → row-level authorization if the resource is per-user/per-facility (mirror `_authorize_case_row_access()`'s pattern) → `log_phi_access(...)` if it touches patient data → add it to `docs/API_REFERENCE.md` in the same change.
- **Machine Learning Constraints**:
  - **CRITICAL**: `scikit-learn` is pinned to an *exact* version (`==1.9.0`) in `requirements.txt`, not `>=`. A trained `.pkl` only reliably unpickles with the scikit-learn version that trained it — a prior unpinned `>=` constraint let a newer scikit-learn install that broke loading the committed model with `ModuleNotFoundError: No module named '_loss'`, a live startup-crashing bug. If you bump the scikit-learn version, you MUST re-run `tools/training/train_classifier.py` and commit the regenerated `.pkl`/`.onnx`/`features_config.json` in the same change.
  - `shap==0.51.0` is also pinned — do not downgrade to 0.46.0 (source build fails on Windows+Python 3.13) or upgrade past 0.51.x without re-verifying the SHAP round-trip on `triage_classifier.pkl`.
  - Never hand-edit `backend/app/ml/models/*.pkl` directly. Use `cd tools/training && python train_classifier.py` (after `pnpm --filter @vitalnet/clinical-core build`) to regenerate — it is the single source of truth for the backend `.pkl` and the frontend `triage_trees.json`/`features_config.json` (offline triage runs in pure JS via `packages/clinical-core/src/treeEvaluator.ts`; there is no onnxruntime dependency). See `backend/app/ml/README.md`, `backend/app/ml/MODEL_CARD.md`, and `docs/DECISIONS.md` §33.
  - Labels and features are no longer computed by a second Python implementation — `tools/training/train_classifier.py` pipes synthetic patients through `packages/clinical-core/cli.mjs`. If you change `packages/clinical-core/src/rules/` or `features.ts`, that's the entire update path; there's nothing to hand-mirror in Python.

### 2. JavaScript/React (Frontend)
- **File Extensions**: Use `.jsx` for React components and `.js` for utility functions/stores.
- **Component Style**:
  - Use functional components with hooks exclusively. Avoid class components.
  - Prefer default exports for page/panel components (`export default DoctorPanel`) and named exports for shared UI components or utilities.
- **Styling**:
  - Strictly use Tailwind CSS v4 utility classes.
  - Do not create custom CSS files unless absolutely necessary (rely on `index.css` for base styles and theme variables).
- **State Management**:
  - Use custom hooks or context (e.g., `authStore.jsx`) for global state.
  - Avoid deep prop-drilling.
- **Naming**:
  - `PascalCase` for component files (`DoctorPanel.jsx`) and component names.
  - `camelCase` for hooks (`useAuth`), variables, and utility functions.
- **Error Handling**:
  - Wrap async API calls in `try/catch` blocks.
  - Use the provided `ToastProvider` to display user-friendly error messages on the UI.
- **i18n**: any new user-facing string in a component that's already been converted (currently `IntakeForm.jsx`, `NavBar.jsx`) must go through `useTranslation()`'s `t()`, with the key added to `en.json` AND `hi.json`/`ta.json` (as an identical placeholder copy, per `docs/DECISIONS.md` §10 — never machine-translate a clinical term yourself). Wire-format values (symptom ids, `chief_complaint`) must stay decoupled from displayed labels — see `IntakeForm.jsx`'s `*_LABEL_KEYS` maps for the pattern.
- **New route/feature checklist**: for anything touching the intake/triage path, the Zod schema lives in `packages/clinical-core/src/schema.ts` (imported into `apps/web`, not redefined there) — extend it there, not in `apps/web`. For other features: stateless fetch wrapper in `api/<domain>.js` using `authHeaders()` → wire into `lib/api.js`'s barrel if other code imports through it → check `api/base.js`'s `ENDPOINT_BACKEND` map for which backend it should hit (almost always `'legacy'` today — apps/api is not live) → add to `docs/API_REFERENCE.md` in the same change if it's a new backend endpoint.

### 3. Database (Supabase)
- **Backend Context**: The backend connects to Supabase via the official `supabase-py` client. Use the service role key for administrative tasks and RLS bypassing, and the anon key when performing actions on behalf of a specific user context. A fresh client is constructed per request rather than a shared client with a swapped auth token — this is deliberate, not an oversight to "optimize" (see `docs/DECISIONS.md` §4).
- **apps/api context**: Deno's `@supabase/supabase-js` — same anon/service-role split as the backend. Prefer a `SECURITY DEFINER` Postgres function (`fn_*`, see `backend/supabase/migrations/phase28_*`) over a new bare service-role call site for any aggregate/cross-user query — service-role usage is meant to stay confined to `/api/admin` + audit writes (`docs/DECISIONS.md` §29).
- **Frontend Context**: The frontend connects via `@supabase/supabase-js`. Ensure RLS (Row Level Security) policies are respected.
- **Migrations**: every schema change is a new numbered `backend/supabase/migrations/phaseN_*.sql` file, written to be idempotent (safe to re-run), shared by both backends. Never edit the schema via the Supabase dashboard UI directly without immediately committing an equivalent migration file. `.github/workflows/db-schema-drift.yml` catches drift between the tracked migrations and both a fresh replay and the live project.

---

## 📖 Keeping documentation current

This repo treats documentation as load-bearing, not an afterthought. If your change would make any of the following wrong, **update it in the same commit/PR**:
- A new top-level directory, route file, service module, or major data flow → `CODEBASE_MAP.md`.
- A new/changed HTTP endpoint → `docs/API_REFERENCE.md`.
- A new environment variable → both `.env.example` files (backend AND frontend, immediately — never commit `.env`/`.env.local` themselves).
- A non-obvious architectural choice, especially one you expect someone to question later → add an entry to `docs/DECISIONS.md`.
- A new test file or testing pattern → `docs/TESTING_STRATEGY.md`.

Stale docs are worse than no docs — they actively mislead the next reader (human or agent). When in doubt, update.

---

## 🤖 Agentic Behavior Directives (Cursor, Copilot, Custom Agents)

1. **Path Construction**: Always use **absolute paths** when reading, writing, or editing files. Resolve relative paths against the repository root (wherever this `AGENTS.md` file lives) — do not assume a specific machine's home directory path.
2. **Context Gathering**: Always use your `read` or `glob` tools to verify the existence and contents of a file before attempting to edit it. Never assume a file's structure.
3. **Environment Variables**: Never commit `.env` or `.env.local` files. If adding new environment variables, update `.env.example` in both backend and frontend directories immediately.
4. **Proactiveness**: When asked to implement a feature, proactively implement the backend route, the frontend integration, and the UI styling without waiting for step-by-step confirmation. Deliver a complete slice of functionality.
5. **No Hallucinations**: If a required library is missing, use `npm install <lib>` or `pip install <lib>` before importing it in the code. Verify dependencies in `package.json` or `requirements.txt`. Before adding a new dependency, check it's actually needed — this repo has had genuinely-unused dependencies removed for exactly this reason (see `docs/DECISIONS.md` and the cleanup history).
6. **Self-Correction (Self-Healing)**: If a bash command fails (e.g., a test fails, linting fails), read the exact error output and correct the code immediately. Do not ask the user for help unless you are completely stuck after multiple debugging attempts.
7. **Clean Commits**: If requested to commit, group related changes logically and write clear, imperative commit messages (e.g., "Add SHAP explanations to DoctorPanel"). See `CONTRIBUTING.md` for the full convention.
8. **Don't guess at blocked decisions**: some FEATURES_ROADMAP items are explicitly scaffolding-only pending a product/vendor decision (SMS aggregator choice, photo-storage backend/consent policy — see `docs/DECISIONS.md` §11) or pending non-engineering review (clinical translation review — §10). Don't "finish" these by guessing at the blocking decision yourself; extend the scaffolding, flag the open decision, and stop there.
