# Fix Log: ROOT-PERF-004

## Issue Solved
Cursor pagination calls from the dashboard were not aligned with the backend composite cursor contract (`before_time + before_priority + before_id`), which could cause repeated/overlapping page loads.

**Bundled Source IDs**: `PERF-004`, `PERF-MEM-R3-003`

## Fix Applied

### Frontend API cursor contract alignment
`frontend/src/api/cases.js`
- `getCases()` now accepts composite cursor input via:
  - `before` object `{ time, priority, id }`
  - or explicit `before_time`, `before_priority`, `before_id`
- serializes all three params when provided.

### Dashboard propagation and dedupe
`frontend/src/pages/Dashboard.jsx`
- tracks `nextCursor`, `nextPriority`, `nextId` from API response
- sends all cursor fields on `loadMore`
- preserves ID-based deduplication when merging pages

## Why This Fix Was Chosen
- Matches backend keyset ordering and tie-break semantics.
- Minimal change surface (API adapter + page state wiring).
- Prevents duplicate work without altering clinical sorting logic.

## Files Changed
- `frontend/src/api/cases.js`
- `frontend/src/pages/Dashboard.jsx`

## Verification
- `npm run build` succeeds.
- Static inspection confirms `before_id` is now transmitted and next cursor fields are persisted between pages.
