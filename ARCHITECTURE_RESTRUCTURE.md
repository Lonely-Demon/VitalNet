# VitalNet — Architecture Restructuring Instructions

> **Version:** 1.0 — Phase 12 (Enterprise Scale Preparation)
> **Scope:** A deep structural reorganization of the VitalNet codebase. This phase transitions the flat prototype architecture into a modular, production-grade package structure. It also introduces structural enhancements like JSON logging, API decomposition, and robust dependency injection.
> **Intended reader:** An AI coding agent or developer executing this rebuild from scratch. Follow each section strictly in order.

> [!IMPORTANT]
> Reading this file requires the codebase to already be at the Phase 11 state (PWA Hardening complete, Zod bounds applied, Drafts persisting).

---

## 0. Pre-Restructure Checklist

Before starting, verify the baseline state:
- [ ] `python backend/test_e2e.py` — all tests pass
- [ ] `npm run build` in `frontend/` — completes successfully
- [ ] `git status` — working tree is completely clean

---

## 1. Backend Package Reorganization

The backend currently sits in a "flat" architecture (all 15 Python files scattered in the root). We will move these into a standard FastAPI `app/` package structure.

### 1.1 Create the Directory Tree
Run the following commands in the backend:

```powershell
cd backend
mkdir app
mkdir app/api
mkdir app/api/routes
mkdir app/core
mkdir app/services
mkdir app/ml
mkdir app/models
mkdir tests
type nul > app/__init__.py
type nul > app/api/__init__.py
type nul > app/api/routes/__init__.py
type nul > app/core/__init__.py
type nul > app/services/__init__.py
type nul > app/ml/__init__.py
type nul > app/models/__init__.py
```

### 1.2 Move Files to their Packages
Move the existing files to their new domains:

**To `app/api/routes/`:**
- `admin_routes.py`
- `analytics_routes.py`
*(Note: Route logic currently inside main.py will be extracted in step 1.3)*

**To `app/core/`:**
- `config.py`
- `auth.py`
- `database.py`

**To `app/services/`:**
- `llm.py`

**To `app/ml/`:**
- `classifier.py`
- `enhanced_classifier.py`
- `clinical_features.py`
- The entire `models/` directory (move to `app/ml/models/`)

**To `app/models/`:**
- `schemas.py`

**To `tests/`:**
- `test_e2e.py`
- `test_direct.py`
- `test_enhanced_classifier.py`

### 1.3 Refactor `main.py` & Extract `cases.py`

Currently, `main.py` contains both the server configuration AND the endpoints for `/api/submit` and `/api/cases`.

1. Create `backend/app/api/routes/cases.py`.
2. Move the `submit_case`, `get_cases`, and `get_my_cases` endpoints from `main.py` into this new file as an `APIRouter`.
3. Move `main.py` itself into `backend/app/main.py`. It should now serve *only* to initialize the FastAPI instance, configure CORS, and include the routers.

---

## 2. Advanced Structural Enhancements (Phase 12.5)

### 2.1 Structured JSON Logging (`app/core/logging.py`)

**Problem:** Standard `print()` or basic string logs are impossible to query efficiently in cloud monitoring platforms (like Datadog, AWS CloudWatch, or Railway).
**Fix:** Implement JSON structured logging.

1. Install: `pip install python-json-logger`
2. Create `backend/app/core/logging.py`:

```python
import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    while logger.handlers:
        logger.handlers.pop()
        
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(module)s %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logging.getLogger("vitalnet")
```
3. Call `setup_logging()` at the very top of `app/main.py`. Replace all `print()` statements across the ML and API layers with `logger.info()` or `logger.warning()`.

### 2.2 Dependency Injection (DI) Refinement

**Problem:** Endpoints manually call `db = get_supabase_for_user(raw_token)` inside the function body.
**Fix:** Convert this into a canonical FastAPI `Depends()`.

In `app/core/database.py`:
```python
from fastapi import Header, HTTPException
from typing import Optional

def get_db_session(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    raw_token = authorization.split(" ", 1)[-1]
    return get_supabase_for_user(raw_token)
```

In `app/api/routes/cases.py` (and others), use it like so:
```python
from fastapi import APIRouter, Depends
from app.core.database import get_db_session

router = APIRouter()

@router.post("/api/submit")
async def submit_case(payload: dict, db = Depends(get_db_session)):
    # DB session is safely injected!
    ...
```

### 2.3 Frontend Architecture: APIs vs. Stores & Vite Aliasing

**Problem:** `frontend/src/lib/api.js` is a monolithic file mixing stateless fetches and stateful offline queues. Furthermore, deep folder structures lead to import hell (`../../../lib/api/cases`).
**Fix:** Implement Vite Aliasing and separate API wrappers from state stores.

1. **Vite Path Aliasing**: Add to `frontend/vite.config.js`:
   ```javascript
   import path from "path"
   export default defineConfig({
     resolve: {
       alias: { "@": path.resolve(__dirname, "./src") },
     },
     // ...
   })
   ```
2. **API vs Store Decomposition**:
   - **`src/api/cases.js`**: Pure, stateless fetch wrappers (`submitCase`, `getCases`).
   - **`src/api/auth.js`**: Stateless Supabase auth helpers.
   - **`src/stores/syncStore.js`**: Move `processQueue` and offline IndexedDB logic here. This separates stateful offline queue management from the raw API contracts.

### 2.4 Configuration Validation & Strict CORS

**Problem:** Relying on `os.getenv` scattered across files and wildcard CORS (`allow_origins=["*"]`) creates security holes and deployment crashes.
**Fix:** 
- **Pydantic Validation:** In `app/core/config.py`, verify that a `BaseSettings` class parses all required keys (e.g., `GROQ_API_KEY`, `SUPABASE_URL`) directly from `.env.local` or environment variables at startup. If any key is missing or malformed, Python will crash on line 1, safeguarding production.
- **Strict CORS:** In `app/main.py`, the `CORSMiddleware` must load its allowed origins dynamically from those Pydantic settings. Avoid wildcard origins.

### 2.5 Global Imports Update

Perform a repository-wide search-and-replace to fix Python imports.
For example:
- `from database import get_supabase_admin` -> `from app.core.database import get_supabase_admin`
- `from llm import generate_briefing` -> `from app.services.llm import generate_briefing`
- `from schemas import TriageCase` -> `from app.models.schemas import TriageCase`

Verify scripts (like `backend/scripts/retrain_and_export.py`) point to `app.ml.clinical_features` instead of `clinical_features`.

---

## 3. Phase 12.6: App Lifecycle & Error Handling

To truly reach enterprise scale, the application must handle startup, teardown, and unhandled crashes elegantly.

### 3.1 FastAPI Lifespan (Non-Blocking ML Load)

**Problem:** Loading `.pkl` models synchronously can block the event loop or cause issues if loaded haphazardly inside route handlers.
**Fix:** Use FastAPI's modern `@asynccontextmanager` to load the `EnhancedTriageClassifier` strictly once at startup.

In `app/main.py`:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.ml.classifier import load_classifier

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load ML models into memory once
    load_classifier()
    yield
    # Shutdown: Clean up resources if necessary

app = FastAPI(title="VitalNet API", lifespan=lifespan)
```

### 3.2 Global Exception Logging

**Problem:** FastAPI's default 500 and 422 exception handlers output raw text to `stderr`, bypassing the new JSON logger.
**Fix:** Override the default handlers to emit structured JSON so alerts trigger correctly in cloud environments.

In `app/main.py` (below the FastAPI initialization):
```python
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("vitalnet")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error", extra={"path": request.url.path, "errors": exc.errors()})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
```

### 3.3 Database Schema Migrations

**Problem:** Refactoring Python files doesn't help if database changes (like the recent `triage_priority` column) are applied manually via the Supabase UI.
**Fix:** Standardize on **Supabase CLI Local Migrations**. 
- Initialize the directory: `supabase init`
- Generate new migrations using: `supabase migration new "add_triage_priority"`
- Execute them against local/remote DBs via `supabase db push`.
- All `.sql` migration files must be tracked in the Git repository alongside the codebase.

### 3.4 PWA Cache Invalidation Strategy

**Problem:** When you deploy a new backend API shape, mobile clients might be permanently trapped on a cached Service Worker hitting deprecated endpoints.
**Fix:** Ensure the frontend handles active invalidations. Use `vite-plugin-pwa` with `registerType: 'prompt'`. Implement an `UpdatePrompt.jsx` component that displays a "New version available. Click here to refresh and update" toast whenever a new Service Worker build is pushed to production.

---

## 4. Phase 12.7: CI/CD Pipeline & Automated Testing

To prevent regressions, the standalone scripts must transition into a CI/CD pipeline that guards the `main` branch.

### 4.1 Pytest Migration
**Problem:** `test_e2e.py` and `test_direct.py` are standalone Python scripts. They don't hook natively into standard CI test runners, making it hard to fail a build automatically.
**Fix:** Migrate to `pytest`.
- Install `pytest`, `pytest-asyncio`, and `httpx`.
- Move the scripts into `backend/tests/` and rename them (e.g., `test_cases_api.py`).
- Replace `print()` verifications with strict `assert` statements covering route responses, Zod/FastAPI validation failures, and database mock states.

### 4.2 GitHub Actions Configuration
**Problem:** Code pushed with failing tests breaks the live deployment.
**Fix:** Add a `.github/workflows/ci.yml` file to enforce validation *before* code hits production.

```yaml
name: VitalNet CI

on:
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install Dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx
      - name: Run Pytest
        run: |
          cd backend
          python -m pytest tests/ -v
        env:
          SUPABASE_URL: ${{ secrets.TEST_SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.TEST_SUPABASE_ANON_KEY }}
          # (Groq/Gemini mocked out during unit tests)

  build-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install and Build
        run: |
          cd frontend
          npm ci
          npm run build
        env:
          VITE_SUPABASE_URL: ${{ secrets.TEST_SUPABASE_URL }}
          VITE_SUPABASE_ANON_KEY: ${{ secrets.TEST_SUPABASE_ANON_KEY }}
          VITE_API_BASE_URL: https://vitalnet-staging.app
```

---

## 5. Phase 13: Operational DevSecOps & Enterprise Readiness

A production codebase is only as good as its operational environment. The following steps safeguard against real-world deployment failures.

### 5.1 Git Branching Model & PR Gatekeeping
**Problem:** Committing directly to `main` defeats the purpose of CI/CD, as tests run *after* the broken code is live.
**Fix:** Enforce a strict Pull Request workflow.
- In GitHub Repo Settings -> Branches -> Add Branch Protection rule for `main`.
- Check **"Require a pull request before merging"**.
- Check **"Require status checks to pass before merging"** and select the `test-backend` and `build-frontend` GitHub Action jobs.
- All future development must happen on feature branches (e.g., `feature/api-split`) and merged via PR.

### 5.2 The "Silent Token Death" UI Fallback
**Problem:** The offline queue handles transient drops gracefully. But if a tablet is offline longer than the Supabase refresh token TTL (e.g., weeks), the queue gets permanent `401`s.
**Fix:** Explicitly handle `requiresLogin: true` from `processQueue`.
- In `App.jsx` or `DoctorPanel.jsx`, monitor the queue status.
- If the token is terminally expired, trigger a fullscreen, un-dismissible modal: *"Your session expired while offline. Please connect to internet and log in to sync your pending cases."*
- Do NOT clear IndexedDB; the data must remain trapped but safe until the new JWT is obtained.

### 5.3 Application Performance Monitoring (APM)
**Problem:** The JSON logs generated in Phase 12.5 are useless if no one is notified when a 500 triggers.
**Fix:** Integrate an APM tool (e.g., Sentry, Datadog) to alert developers actively.
- Create a Sentry project.
- `pip install sentry-sdk` and initialize it alongside the FastAPI app in `app/main.py`.
- Ensure it captures the unhandled exceptions generated by the new global exception handler so developers get an immediate Slack/SMS alert on failure.

### 5.4 Database Disaster Recovery (PITR)
**Problem:** Executing `supabase db push` on a production database carries a huge risk of accidental `DROP TABLE` or data corruption.
**Fix:** Point-In-Time Recovery.
- Ensure the production Supabase project is on a tier supporting PITR (Point-In-Time Recovery).
- Before executing any major schema migrations, verify the automated pre-deployment backup snapshot holds.

---

## 6. Final Verification

1. **Backend Tests**: Run `python -m pytest tests/` from the `/backend` root directory.
2. **Frontend Build**: Run `npm run build` from the `/frontend` directory.
3. **End-to-End**: Start `uvicorn app.main:app --port 8000` and manually submit one case via the frontend to confirm the DI route injections and JSON logger are functioning in harmony.

```powershell
git commit -m "Refactor: Phase 12 structure, dependencies, and DevSecOps integrations"
```
