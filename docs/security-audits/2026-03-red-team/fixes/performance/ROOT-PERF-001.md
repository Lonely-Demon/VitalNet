# Fix Log: ROOT-PERF-001

## Issue Solved
The frontend chunking/layout strategy was incomplete:
- vendor splitting was not deterministic across all dependency paths,
- role panels were lazy in `App.jsx`, but heavy panel internals were still eagerly imported.

This increased cold-start JS and reduced cache reuse for repeat loads.

**Bundled Source IDs**: `PERF-001`, `PERF-BUNDLE-R3-001`, `PERF-BUNDLE-R3-002`

## Fix Applied

### 1) Deterministic manual chunking in Vite
Updated `frontend/vite.config.js` to use function-based `manualChunks(id)` with normalized module paths (`id.replace(/\\/g, '/')`) and stable bucket names:
- `vendor-react`
- `vendor-supabase`
- `vendor-onnx`
- `vendor-charts`
- `vendor-date`
- `vendor-misc`

Also kept `chunkSizeWarningLimit: 2000`.

### 2) Lazy role panel loading in App
`frontend/src/App.jsx` now lazy-loads role panels with explicit suspense fallback:
- `ASHAPanel`, `DoctorPanel`, `AdminPanel` via `lazy(() => import(...))`
- `<Suspense fallback={<PanelFallback />}>`

### 3) Lazy heavy tab/page content inside panels
To avoid pulling all admin/new-case code immediately:
- `frontend/src/panels/AdminPanel.jsx` lazy-loads `AdminUsers`, `AdminFacilities`, `AdminStats`, `AnalyticsDashboard`
- `frontend/src/panels/ASHAPanel.jsx` lazy-loads `IntakeForm`

## Why This Fix Was Chosen
- Deterministic chunk grouping improves long-term browser cache hit rates.
- Lazy loading aligns shipped JS with current user role/tab intent.
- Changes are isolated to bundling/import boundaries (low regression risk).

## Files Changed
- `frontend/vite.config.js`
- `frontend/src/App.jsx`
- `frontend/src/panels/AdminPanel.jsx`
- `frontend/src/panels/ASHAPanel.jsx`

## Verification
- `npm run build` (frontend)
- Build output confirms separate chunks: `vendor-react`, `vendor-supabase`, `vendor-onnx`, and split panel/tab chunks (`AdminPanel-*`, `IntakeForm-*`, etc.)
