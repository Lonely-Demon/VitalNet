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
├── lib/                             Supabase client, unified offline outbox
│                                    (outbox.js) + its shared IndexedDB opener
│                                    (offlineDB.js), connectivity probe, Web
│                                    Push subscription helper, api.js barrel
├── stores/syncStore.js              Online/offline submit — a thin client over
│                                    lib/outbox.js (background sync drain loop)
├── api/                             Stateless per-domain fetch wrappers, incl.
│                                    base.js's per-endpoint edge-vs-legacy resolver
├── hooks/                           useLocalTriage, useDraftSave, useRealtimeCases,
│                                    useRealtimeReferrals, useVoiceInput
├── utils/triageClassifier.js       Offline model loading/warmup ONLY (fetches
│                                    /models/*.json) — the clinical logic itself
│                                    (rules, features, tree eval, contraindications)
│                                    is @vitalnet/clinical-core, not mirrored here
│                                    (see ../docs/DECISIONS.md §33)
├── pages/, panels/, components/     UI — role-specific panels are React.lazy()-loaded
public/
├── sw-push.js                       Web Push service-worker handlers
└── models/                          Offline triage model artifacts (tree JSON, ~1 MB) —
                                       the same artifact apps/api/.../_shared/models/ bundles
tests/                               Playwright E2E (offline.spec.js)
```

Full file-by-file detail: [../CODEBASE_MAP.md](../CODEBASE_MAP.md) §4.

## Common commands

```bash
npm run dev                  # dev server
npm run build                # production build — also the main regression check
npm run preview               # preview a production build locally
npx playwright test tests/offline.spec.js   # offline-flow E2E (needs a running dev server)
```

## Triage logic lives in one place

`@vitalnet/clinical-core` (`packages/clinical-core`, a pnpm workspace
dependency resolved via `workspace:*`) is the single source of clinical
truth: the deterministic rules engine, 43-feature engineering, the offline
tree evaluator, contraindication checks, and the `IntakeForm` Zod schema.
`useLocalTriage`/`utils/triageClassifier.js` call the SAME `triage()`
function that `apps/api`'s `POST /api/submit` will eventually call
server-side — there is only one implementation, not two kept in sync by
hand, so the two paths can never silently drift apart the way the old
hand-mirrored files could.

**Mode: `hybrid`, not `rules_first`.** This deliberately does NOT match
`apps/api` (which runs `rules_first`) — it matches the backend that's
actually live today, `backend/app/` (FastAPI), which is still
model-primary. The two modes disagree on 0.88% of cases
(`packages/clinical-core/test/conformance/report.md`), and the
AUTHORITATIVE, persisted tier always comes from whichever backend
`POST /api/submit` currently resolves to — the raw form is what's queued
offline, not the locally-computed tier (see "Offline: the unified outbox"
below). Showing a `rules_first` preliminary offline, before
`docs/CLINICAL_REVIEW.md`'s sign-off and before the server itself cuts
over, would let a preliminary tier disagree with what the case becomes on
sync. `runTriage()` switches to `hybrid` alongside the real server cutover,
not before it. When the model can't be loaded offline, `hybrid` mode has
no rules-only fallback (the model is authoritative for the non-override
band) — `runTriage()` falls back to the override-only safety net (identical
in both modes) and reports `triageLevel: null` ("pending — will be
triaged on sync") rather than guessing.

`utils/triageClassifier.js` itself owns only what's genuinely
browser-specific: fetching + caching `/models/triage_trees.json` and
`/models/features_config.json`.

This replaced four previously hand-mirrored files (`clinicalRules.js`,
`triageClassifier.js`'s own `buildFeatureMap`, `treeEvaluator.js`,
`validation.js`, `patientKey.js`) and the four apps/web-side parity test
suites that existed solely to catch drift between the JS mirror and the
Python original — see `packages/clinical-core/README.md` and
`../docs/DECISIONS.md` §33 for the full migration rationale and
conformance evidence. Clinical-rule changes now happen in
`packages/clinical-core/src/` and are verified with
`pnpm --filter @vitalnet/clinical-core test`, not an apps/web script.

## Offline: the unified outbox

`lib/outbox.js` is a generic event queue (IndexedDB, `{ event_id, type,
payload, created_at, attempts, status, last_error }`) — `syncStore.js`'s
`submitCase`/`processQueue` are a thin client over it. Only
`type: 'case.submit'` exists today (doctor actions stay online-only), but
the store itself isn't case-specific, so a future offline-capable action
can reuse it without another IndexedDB version bump. `event_id` is the
same uuid as `case_records.client_id` and the `X-Event-Id` header
apps/api's idempotency middleware dedupes on — one id end to end, not
three independently-generated ones. A permanently-failing (4xx) event is
dead-lettered (`status: 'dead'`), not silently dropped — `OfflineBanner.jsx`
surfaces dead letters with retry/discard actions.

## Deployment

Includes `vercel.json` for SPA routing. See the root README's Deployment
section for required environment variables.
