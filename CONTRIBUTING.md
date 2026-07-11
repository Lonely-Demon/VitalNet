# Contributing to VitalNet

This document covers the *process* of contributing — branch strategy, PR
workflow, commit conventions, and CI expectations. For *what* to build, see
`FEATURES_ROADMAP.md`. For code style, see `AGENTS.md`. For *why* things are
built the way they are, see `docs/DECISIONS.md`.

## Branch strategy

Three long-lived branches for building, testing, and deploying what's
already shipped:

| Branch | Purpose | How it's updated |
|---|---|---|
| `dev` | Active development | Direct pushes for small changes, or a short-lived feature branch merged via PR (squash) |
| `main` | Periodically synced to a verified-good `dev` state | PR only, squash-merge, favoring `dev`'s content on conflict |
| `test` | Pre-production staging | As needed, per deployment process |

**Work on `dev`.** Don't develop directly on `main` — see
`docs/DECISIONS.md` §9 for the full rationale and the exact recovery
procedure if `main` and `dev` have drifted.

Both `main` and `dev` reject plain merge commits at the GitHub level —
PRs merge via **squash or rebase only**. GitHub auto-deletes feature
branches on merge; don't bother deleting them yourself.

**Plus one long-lived branch for major reforms**: `experimental` — large,
multi-phase architectural rewrites (the kind that leave the repo in an
intermediate, sometimes-broken state across many commits, e.g. a language
migration or a rearchitecture of the triage pipeline). This work does NOT
develop on `dev` and is not merged back automatically — `dev`/`main`/`test`
stay solely for building, testing, and deploying what's already shipped and
verified. See `docs/DECISIONS.md` §32 for the rationale and the promotion
path (a reviewed PR against `dev`, only once a reform phase is complete and
independently verified — never a silent merge).

## Opening a PR

1. Branch off `dev`: `git checkout -b feature/short-description dev`.
2. Make your change. Follow `AGENTS.md`'s code-style conventions and the
   "new route/feature checklist" in each language section.
3. Run the relevant verification before opening the PR (see
   `docs/TESTING_STRATEGY.md` for the full list) — at minimum:
   ```bash
   cd backend && ruff check . && pytest tests/ --ignore=tests/test_e2e.py -v
   cd frontend && npm run build && npm run test:parity && npm run test:feature-parity
   ```
4. Update documentation in the same PR if your change makes any of it wrong
   — see AGENTS.md's "Keeping documentation current" section. A PR that
   changes behavior without touching the doc that describes that behavior
   should be treated as incomplete, not "docs as a follow-up."
5. Push and open a PR against `dev`. CI runs lint (backend), the pytest
   suite, a frontend build, and CodeQL analysis automatically.
6. Once CI is green and (if applicable) reviewed, squash-merge.

### A note on CI and PR base branches

`pull_request`-triggered GitHub Actions workflows run using the workflow
file **from the base branch**, not the PR's head branch — this is a
GitHub security feature (a PR can't silently rewrite the CI that gates it).
Practically: if you change `.github/workflows/ci.yml` itself, that change
only takes effect for *future* PRs once it's merged into the base branch —
your own PR will still run against the *old* workflow file.

## Commit message conventions

Imperative mood, concise summary line, body explaining *why* not *what* (the
diff already shows what changed):

```
Add response-time SLA dashboard to analytics endpoints

PHC administrators need to know if EMERGENCY cases are actually being
reviewed within the target window, not just how many cases exist.
```

Avoid vague messages ("fix stuff", "updates"). Group related changes into
one logical commit rather than a stream of "wip" commits — squash locally
before pushing if you iterated a lot.

## What CI checks (and why a PR might not merge cleanly)

- **`lint-backend`** — `ruff check .` must pass with zero findings.
- **`test-backend`** / **pytest suite** — the offline test suite
  (`tests/ --ignore=tests/test_e2e.py`) must pass. This includes the ML
  safety-property tests, admin-route authorization sweep, and the
  online/offline feature-parity check.
- **`build-frontend-pr`** — `npm run build` must succeed.
- **CodeQL** (`Analyze (python)`, `Analyze (javascript-typescript)`,
  `Analyze (actions)`) — flags new security findings introduced by the
  diff. If you get a finding on code you're confident is safe/intentional
  (e.g. audit-log logging, a synthetic-data-only test print), suppress it
  inline with `# codeql[query-id]` on the **exact flagged line** (not the
  legacy `lgtm[query-id]` syntax — GitHub's current CodeQL doesn't honor
  that one; see `docs/DECISIONS.md` §13) with a comment explaining why,
  rather than silencing it silently.

CodeQL comparing against a stale/divergent base branch can flag
already-reviewed code as "new" — if you see a large batch of alerts on code
you recognize as pre-existing and already-accepted, check whether the PR's
base branch is actually up to date before assuming something regressed.

## Adding a database migration

1. Create `backend/supabase/migrations/phaseN_description.sql` (next
   sequential number).
2. Write it idempotently (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT
   EXISTS`, `DROP POLICY IF EXISTS` before `CREATE POLICY`, etc.) — it must
   be safe to run more than once.
3. Include RLS policies for any new table in the same migration — don't
   ship a table without RLS and follow up "later."
4. Run it against your own Supabase project's SQL editor to verify it
   applies cleanly, then update `CODEBASE_MAP.md` §5 (the table list and
   the ER diagram) and `docs/API_REFERENCE.md` if it's paired with a new
   endpoint.
5. Never edit the schema via the Supabase dashboard UI directly and skip
   the migration file — the migration files are the canonical schema
   source, not whatever the live project happens to have.

## Retraining the ML model

See the "Regenerating the ML classifier" section in `README.md` and
`backend/app/ml/README.md`. The short version: one command
(`python scripts/train_classifier.py`) regenerates the backend `.pkl`, the
frontend `triage_trees.json`/`features_config.json`, and the golden-vector
fixtures together — never regenerate one without the others, and never
hand-edit any of the generated artifacts.

## Questions

If something in the codebase looks like it should be simplified or removed
and you're not sure why it's there, check `docs/DECISIONS.md` first — a
surprising number of "this looks unnecessary" observations turn out to be
solved problems with the solution left in place. If it's genuinely not
covered there, that's itself worth flagging (and probably worth adding an
entry once resolved).
