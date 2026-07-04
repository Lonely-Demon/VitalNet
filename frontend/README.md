# VitalNet Frontend

React 19 + Vite 7 + Tailwind CSS v4 PWA. No TypeScript (plain `.jsx`/`.js`).
For full project context, start at the repo root
[README.md](../README.md) and [CODEBASE_MAP.md](../CODEBASE_MAP.md) §4.

## Quick start

```bash
npm install
cp .env.example .env.local      # fill in Supabase URL/anon key + backend API URL
npm run dev
```
Visit http://localhost:5173.

## Layout

```
src/
├── main.jsx / i18n.js / App.jsx    Entry point, i18n init, role-based routing
├── locales/                        i18n translation source (en.json canonical;
│                                    hi/ta are placeholders — see locales/README.md)
├── store/authStore.jsx             Auth/session state
├── lib/                             Supabase client, offline queue, connectivity probe,
│                                    Web Push subscription helper, api.js barrel
├── stores/syncStore.js              Online/offline submit + background sync
├── api/                             Stateless per-domain fetch wrappers
├── hooks/                           useLocalTriage, useDraftSave, useRealtimeCases,
│                                    useRealtimeReferrals, useVoiceInput
├── utils/                           Offline triage engine (mirrors the backend ML
│                                    pipeline exactly — see ../docs/DECISIONS.md §2),
│                                    Zod validation, image compression scaffold
├── pages/, panels/, components/     UI — role-specific panels are React.lazy()-loaded
public/
├── sw-push.js                       Web Push service-worker handlers
└── models/                          Offline triage model artifacts (tree JSON, ~1 MB)
tests/                               Parity tests (CI) + Playwright E2E
```

Full file-by-file detail: [../CODEBASE_MAP.md](../CODEBASE_MAP.md) §4.

## Common commands

```bash
npm run dev                  # dev server
npm run build                # production build — also the main regression check
npm run preview               # preview a production build locally
npm run test:parity           # offline tree-evaluator vs. server model (CI)
npm run test:feature-parity   # offline feature engineering vs. server (CI)
npx playwright test tests/offline.spec.js   # offline-flow E2E (needs a running dev server)
```

## The two things that must never silently diverge

1. **Triage logic** (`utils/triageClassifier.js`, `treeEvaluator.js`,
   `clinicalRules.js`) mirrors the backend's ML pipeline exactly — any
   change to `backend/app/ml/clinical_features.py` or the safety-net rules
   must be ported here in the same change, then verified with
   `npm run test:parity` and `npm run test:feature-parity`.
2. **Form validation** (`utils/validation.js`, Zod) mirrors
   `backend/app/models/schemas.py::IntakeForm`'s bounds — a new field or
   bound on one side needs the matching change on the other.

See `../docs/DECISIONS.md` §2 for why two implementations of the same
logic is the intended design here, not duplication to clean up.

## Deployment

Includes `vercel.json` for SPA routing. See the root README's Deployment
section for required environment variables.
