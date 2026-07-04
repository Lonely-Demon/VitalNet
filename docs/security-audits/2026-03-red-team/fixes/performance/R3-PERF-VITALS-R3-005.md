# Fix Log: R3-PERF-VITALS-R3-005

## Issue Solved
"Load More" could trigger redundant first-page/overlapping fetch work because the dashboard only passed a partial cursor and did not fully align with backend pagination fields.

## Fix Applied
In `frontend/src/pages/Dashboard.jsx`:
- persisted and forwarded `nextCursor`, `nextTriagePriority`, and `nextId`
- sent composite cursor payload on `loadMore`
- kept merge deduplication by `id` to avoid duplicate cards when realtime and pagination intersect.

In `frontend/src/api/cases.js`:
- extended `getCases()` parameter handling to include `before_id` and object-form cursor.

## Why This Fix Was Chosen
- Resolves redundant page-fetch behavior without changing API route shapes.
- Maintains stable UX and avoids duplicate render work on constrained devices.

## Files Changed
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/api/cases.js`

## Verification
- `npm run build` passes.
- Code-level check confirms `before_id` and composite cursor values are propagated end-to-end.
