# ROOT-CHAOS-009: Observability for Degraded Analytics Responses

## Issue Summary
When analytics queries fail partially, there was no observability to track which queries failed and when degradation occurred.

This is a MEDIUM (P2) reliability issue representing "cascading failure risks, recovery path gaps".

## Fix Applied

### Backend Changes
Enhanced `backend/app/api/routes/analytics_routes.py` with:

1. **Degradation indicators**: Added `_degraded` flag to response when any query fails
2. **Failure tracking**: Added `_failed_queries` array listing which queries failed
3. **Logging**: Logs warnings when queries timeout or fail

### Frontend Changes
Enhanced `frontend/src/api/analytics.js` with:

1. **Degradation detection**: Checks for `_degraded` and `_fallback` flags
2. **Error logging**: Logs degradation events for observability
3. **Fallback tracking**: Includes `_error` and `_fallback` in fallback responses

## Files Changed

### Backend
- `backend/app/api/routes/analytics_routes.py`
  - Added `_degraded` and `_failed_queries` to response
  - Added logging for query failures

### Frontend
- `frontend/src/api/analytics.js`
  - Added degradation detection and logging
  - Added `_error` and `_fallback` to fallback responses

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. **Metrics export** - Would require additional infrastructure
2. **Alerting** - Would require additional setup

**Chosen approach:**
- Simple flag-based observability
- Leverages existing logging infrastructure
- No new dependencies

## Verification

```bash
# Check syntax
python -m py_compile backend/app/api/routes/analytics_routes.py

# Frontend check
cd frontend && npx biome check src/api/analytics.js
```

## Related Issues
This fix addresses observability for:
- ROOT-CHAOS-005: Analytics summary graceful degradation
- ROOT-CHAOS-006: Emergency rate endpoint
- ROOT-CHAOS-007: Frontend retry logic
- ROOT-CHAOS-008: Database module documentation