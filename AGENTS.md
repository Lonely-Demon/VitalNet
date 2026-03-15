# VitalNet Agent Instructions (AGENTS.md)

This document provides essential instructions, commands, and code style guidelines for agentic coding assistants (e.g., Claude, Cursor, Copilot, Antigravity) operating in the VitalNet repository. Always refer to these guidelines before modifying code, reading context, or running commands.

## 🏗️ Project Architecture Overview
- **Backend**: Python 3.13, FastAPI, Supabase (PostgreSQL), Groq LLM, scikit-learn (Machine Learning triage).
- **Frontend**: React 19, Vite, Tailwind CSS v4, PWA support, JS/JSX (no TypeScript).
- **Monorepo Structure**: Independent `/backend` and `/frontend` directories.

---

## 🚀 Build, Run, and Lint Commands

### Backend (Python/FastAPI)
Always operate within a virtual environment (`python -m venv venv && source venv/bin/activate`).
- **Install Dependencies**: `pip install -r backend/requirements.txt`
- **Run Server**: `cd backend && python -m uvicorn main:app --reload --port 8000`
- **Linting**: `cd backend && ruff check .`
- **Formatting**: `cd backend && ruff format .`
- **Regenerate ML Models**: `cd backend && python scripts/retrain_and_export.py`

### Frontend (React/Vite)
- **Install Dependencies**: `cd frontend && npm install`
- **Run Dev Server**: `cd frontend && npm run dev`
- **Build for Production**: `cd frontend && npm run build`
- **Preview Build**: `cd frontend && npm run preview`

---

## 🧪 Testing Guidelines

The backend currently uses standalone Python scripts for testing rather than a complex `pytest` suite. Use these scripts to verify functionality.

- **Run all E2E Tests**:
  ```bash
  cd backend && python test_e2e.py
  ```
- **Run a Single Test / Direct Test**:
  To test the enhanced classifier directly without spinning up the server:
  ```bash
  cd backend && python test_direct.py
  ```
- **Adding New Tests**: 
  Follow the pattern of creating a `test_<feature>.py` file and executing it directly with Python. Include detailed `print()` statements for test steps, as this is the primary debugging method in this repo.
- **If introducing Pytest**: 
  Run specific tests using `cd backend && pytest test_<feature>.py -v`. Ensure tests do not mutate production Supabase data.

---

## 🧑‍💻 Code Style & Conventions

### 1. Python (Backend)
- **Async Framework**: FastAPI routes should heavily utilize `async def` and `await` for I/O bound operations (database calls, LLM generation).
- **Typing**: Use standard Python type hints extensively. E.g., `async def process_data(user_id: str, payload: dict) -> list:`. Pydantic models (in `schemas.py`) should be used for all request/response validation.
- **Imports**: 
  1. Standard library imports
  2. Third-party library imports (`fastapi`, `pydantic`, `supabase`)
  3. Local application imports (`from database import ...`)
- **Naming**: 
  - `snake_case` for variables, functions, and file names.
  - `PascalCase` for Pydantic models and classes.
  - `UPPER_SNAKE_CASE` for global constants.
- **Error Handling**: 
  - Use FastAPI's `HTTPException` for expected API errors (e.g., `raise HTTPException(status_code=404, detail="Not found")`).
  - Catch specific exceptions rather than bare `except Exception:`.
  - Log errors clearly to standard output before returning them to the user.
- **Machine Learning Constraints**:
  - **CRITICAL**: Do *not* change `shap==0.51.0` or `scikit-learn` versions in `requirements.txt`. They are highly sensitive to Python 3.13 and Windows compatibility.
  - Avoid modifying `backend/models/*.pkl` directly. Use `backend/scripts/retrain_and_export.py` to regenerate models if features change.

### 2. JavaScript/React (Frontend)
- **File Extensions**: Use `.jsx` for React components and `.js` for utility functions/stores.
- **Component Style**: 
  - Use functional components with hooks exclusively. Avoid class components.
  - Prefer default exports for page/panel components (`export default DoctorPanel`) and named exports for shared UI components or utilities.
- **Styling**: 
  - Strictly use Tailwind CSS v4 utility classes.
  - Do not create custom CSS files unless absolutely necessary (rely on `index.css` for base styles and theme variables).
- **State Management**: 
  - Use custom hooks or context (e.g., `authStore.js`) for global state.
  - Avoid deep prop-drilling.
- **Naming**: 
  - `PascalCase` for component files (`DoctorPanel.jsx`) and component names.
  - `camelCase` for hooks (`useAuth`), variables, and utility functions.
- **Error Handling**: 
  - Wrap async API calls in `try/catch` blocks.
  - Use the provided `ToastProvider` to display user-friendly error messages on the UI.

### 3. Database (Supabase)
- **Backend Context**: The backend connects to Supabase via the official `supabase-py` client. Use the service role key for administrative tasks and RLS bypassing, and the anon key when performing actions on behalf of a specific user context.
- **Frontend Context**: The frontend connects via `@supabase/supabase-js`. Ensure RLS (Row Level Security) policies are respected.

---

## 🤖 Agentic Behavior Directives (Cursor, Copilot, Custom Agents)

1. **Path Construction**: Always use **absolute paths** when reading, writing, or editing files. Resolve relative paths against the workspace root (`/home/dharshan/VitalNet/`).
2. **Context Gathering**: Always use your `read` or `glob` tools to verify the existence and contents of a file before attempting to edit it. Never assume a file's structure.
3. **Environment Variables**: Never commit `.env` or `.env.local` files. If adding new environment variables, update `.env.example` in both backend and frontend directories immediately.
4. **Proactiveness**: When asked to implement a feature, proactively implement the backend route, the frontend integration, and the UI styling without waiting for step-by-step confirmation. Deliver a complete slice of functionality.
5. **No Hallucinations**: If a required library is missing, use `npm install <lib>` or `pip install <lib>` before importing it in the code. Verify dependencies in `package.json` or `requirements.txt`.
6. **Self-Correction (Self-Healing)**: If a bash command fails (e.g., a test fails, linting fails), read the exact error output and correct the code immediately. Do not ask the user for help unless you are completely stuck after multiple debugging attempts.
7. **Clean Commits**: If requested to commit, group related changes logically and write clear, imperative commit messages (e.g., "Add SHAP explanations to DoctorPanel").
