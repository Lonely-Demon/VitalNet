# Fix Log: ROOT-PERF-007

## Issue Solved
`/api/health` responses lacked explicit cache headers, causing unnecessary repeated health fetch load from clients and probes.

## Fix Applied
In `backend/app/main.py`, health endpoint responses now always include:

```http
Cache-Control: public, max-age=30, stale-while-revalidate=30
```

Applied to both:
- healthy `200` response
- degraded `503` response

## Why This Fix Was Chosen
- Health status is safe for short-lived caching.
- Reduces repeated request pressure while keeping freshness windows tight.
- Minimal, production-safe change localized to endpoint response construction.

## Files Changed
- `backend/app/main.py`
- `backend/tests/test_health_endpoint.py` (added header assertion)

## Verification
- Frontend build succeeds (domain validation baseline).
- Backend syntax compile succeeds for updated files.
- Test includes explicit `Cache-Control` assertion for `/api/health`.
