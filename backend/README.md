# VitalNet Backend

FastAPI (Python 3.13) service — API, ML triage classifier, LLM briefing
generation. For full project context, start at the repo root
[README.md](../README.md) and [CODEBASE_MAP.md](../CODEBASE_MAP.md) §3.

## Quick start

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env.local      # fill in Supabase + Groq credentials
python -m uvicorn app.main:app --reload --port 8000
```
Verify at http://localhost:8000/api/health.

## Layout

```
app/
├── main.py              Entry point: middleware, routers, exception handlers
├── core/                 Config, auth, database, audit logging, correlation IDs
├── api/routes/           HTTP endpoints — see ../docs/API_REFERENCE.md
├── models/schemas.py     Pydantic request/response contracts
├── ml/                   Classifier + feature engineering — see app/ml/README.md
└── services/             LLM briefing, Web Push, SMS-fallback scaffolding
scripts/                  Training, export, retraining pipelines
supabase/migrations/      Version-controlled schema (canonical source)
tests/                    pytest suite + standalone smoke/integration scripts
```

Full file-by-file detail: [../CODEBASE_MAP.md](../CODEBASE_MAP.md) §3.

## Common commands

```bash
ruff check .                                          # lint (zero-tolerance in CI)
pytest tests/ --ignore=tests/test_e2e.py -v            # offline test suite
PYTHONPATH=. python tests/test_direct.py               # classifier-only smoke test
python tests/test_e2e.py                               # full integration (needs live server)
python scripts/train_classifier.py                     # regenerate the ML model (see below)
```

## The ML model is trained and committed, not built at deploy time

Only regenerate it if you change `app/ml/clinical_features.py` or
`scripts/train_classifier.py`:
```bash
pip install -r requirements-train.txt
python scripts/train_classifier.py
```
This single command is the source of truth for the backend `.pkl`, the
frontend's `triage_trees.json`/`features_config.json`, and the golden-vector
test fixtures — regenerate them together, never independently. See
`app/ml/README.md`, `app/ml/MODEL_CARD.md`, and `../docs/DECISIONS.md`
§§2-3, §12.

## Deployment

Pre-configured for Railway (`Procfile`, `railway.toml`, `runtime.txt`). See
the root README's Deployment section for required environment variables.
