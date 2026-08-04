# VitalNet — New Developer Onboarding

A literal first-day walkthrough: clone → run locally → understand the
shape of the code → make a trivial change → verify it → open a PR. If
you've done this before on other projects, skim for VitalNet-specific
gotchas (marked ⚠️) and skip the rest.

## 0. Before you start

Read, in this order, don't skip:
1. `README.md` — what this is and why.
2. This document.
3. `CODEBASE_MAP.md` §1 (the one-paragraph summary) and the system
   architecture diagram right after it.

You do **not** need to read `docs/DECISIONS.md` or `docs/API_REFERENCE.md`
cover-to-cover on day one — those are reference docs you'll come back to
when something specific comes up ("why is this built this way?", "what
does this endpoint expect?"). Do skim their tables of contents so you know
they exist.

## 1. Get the code running

### 1.1 Clone and check the branch
```bash
git clone <this-repo>
cd VitalNet
git branch -a
```
⚠️ You should be on `dev` for any new work — see `CONTRIBUTING.md`. `main`
is not the active development branch here, unlike many repos' conventions.

### 1.2 Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
You'll need a Supabase project (free tier is fine for local dev) — create
one at supabase.com, then run every file in `backend/supabase/migrations/`
**in numeric order** against its SQL editor. Copy `backend/.env.example` to
`backend/.env.local` and fill in your project's URL/keys plus a Groq API
key (free tier at console.groq.com).

```bash
python -m uvicorn app.main:app --reload --port 8000
```
Visit http://localhost:8000/api/health — you should see
`{"status": "ok", "version": "..."}`. If you see `"degraded"`, check the
terminal output: either the database connection or the ML classifier
failed to load, and the log will say which.

### 1.3 Frontend
```bash
cd frontend
npm install
```
Copy `frontend/.env.example` to `frontend/.env.local`, fill in the same
Supabase URL/anon key and `VITE_API_BASE_URL=http://localhost:8000`.
```bash
npm run dev
```
Visit http://localhost:5173.

### 1.4 Seed test accounts
See `Context/test_credentials.md` for the standard test logins. If they
don't exist yet in your fresh Supabase project, you'll need to create them
via Supabase's dashboard (Auth → Users) with matching `profiles` rows
(role, `facility_id`), or use `backend/seed_user.py` for the doctor account
specifically (read its warning banner first).

**Checkpoint**: you can log in as the ASHA test account, submit a test
case, and see it show up in the doctor dashboard (log in as the doctor
account in a different browser/incognito window) with a triage tier
already assigned.

## 2. Orient yourself in the code

Don't try to read everything. Instead:

1. Open `CODEBASE_MAP.md` and find the section for whatever you're about
   to touch (§3 backend, §4 frontend, §5 database).
2. If you're touching an API endpoint, check `docs/API_REFERENCE.md` for
   its exact contract first — don't infer it from the frontend call site,
   confirm against the actual Pydantic model.
3. If something looks like it should obviously be simplified or removed,
   check `docs/DECISIONS.md` before touching it — a lot of "this looks
   unnecessary" turns out to be a solved problem (see its entries on the
   per-request Supabase client, the CSRF token design, the safety-net
   layering).

## 3. Make a trivial change (dry run of the whole workflow)

A good first PR is small and touches both halves of the stack lightly, so
you exercise the real workflow without much risk. Suggestion: add a new
field to the admin stats endpoint, or adjust a UI label — anything you can
verify by eye.

```bash
git checkout -b feature/my-first-change dev
```

Make your change. Then, before committing:

```bash
# Backend, if you touched it:
cd backend && ruff check . && pytest tests/ --ignore=tests/test_e2e.py -v

# Frontend, if you touched it:
cd frontend && npm run build
```

⚠️ If you touched anything in `app/ml/clinical_features.py` or
`frontend/src/utils/triageClassifier.js`, you must also run:
```bash
cd frontend && npm run test:parity && npm run test:feature-parity
```
These are the online/offline consistency guarantee — see
`docs/TESTING_STRATEGY.md`. A failure here is not a flaky test to retry
past; it means the browser and the server would now disagree about a
patient's triage.

## 4. Commit and open a PR

```bash
git add <files>
git commit -m "Short imperative summary of the change"
git push -u origin feature/my-first-change
```
Open a PR against `dev` (not `main`). See `CONTRIBUTING.md` for the commit
message convention and what CI will check. If your change makes any part
of `CODEBASE_MAP.md`, `docs/API_REFERENCE.md`, or a `.env.example` file
inaccurate, update that in the same PR — see AGENTS.md's "keeping
documentation current" section.

## 5. Common first-week gotchas

- **`main` is not where you work.** If you're used to `main`/`master` being
  the active branch, this will trip you up once. `dev` is it here.
- **The ML model is trained and committed, not built on deploy.** Don't
  expect `scripts/train_classifier.py` to run automatically — it's a
  manual step you run only when you intentionally change the feature
  engineering or retrain on new data. See `README.md`'s "Regenerating the
  ML classifier" section.
- **Two implementations of the same triage logic exist on purpose**
  (Python for online, JS for offline) — this is not duplication to clean
  up, it's the whole point of the offline-first design. See
  `docs/DECISIONS.md` §2.
- **`scikit-learn`/`shap` versions are pinned exactly.** Don't bump them
  casually — see AGENTS.md's ML constraints section.
- **Hindi/Tamil translations are placeholders, not bugs.** If you notice
  the language switcher doesn't actually translate anything yet, that's
  intentional — see `docs/DECISIONS.md` §10.
- **Some roadmap features have no live endpoint on purpose.** SMS fallback
  and photo attachments are scaffolding-only pending product decisions —
  don't be surprised the schema exists but nothing calls it yet.

## 6. Where to ask questions

If you're stuck on *why* something is built a certain way, check
`docs/DECISIONS.md` first, then `docs/security-audits/` (historical
context, read as archaeology not current state), then ask directly.
