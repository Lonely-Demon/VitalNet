# ROOT-CHAOS-006: Emergency Rate Endpoint Graceful Degradation

## Issue Summary
The emergency rate analytics endpoint had no graceful degradation when the database query fails. A query timeout or error would result in no data for the trend indicator.

This is a MEDIUM (P2) reliability issue representing "cascading failure risks, recovery path gaps".

## Fix Applied

### Backend Changes
Added graceful degradation to `backend/app/api/routes/analytics_routes.py`:

1. **Query timeout**: Added 10-second timeout using `asyncio.wait_for()`
2. **Error handling**: Catches both timeout and general exceptions
3. **Empty fallback**: Returns empty weeks array when query fails
4. **Logging**: Logs warning for observability

### Frontend Changes
Added resilience to `frontend/src/api/analytics.js`:

1. **Retry logic**: Uses `fetchWithRetry` with 2 retries and 15s timeout
2. **Fallback response**: Returns graceful degradation structure when all retries fail

## Files Changed

### Backend
- `backend/app/api/routes/analytics_routes.py`
  - Added timeout handling to `get_emergency_rate` endpoint
  - Returns empty weeks array on failure

### Frontend
- `frontend/src/api/analytics.js`
  - Added retry logic with `fetchWithRetry`
  - Added fallback response structure

## Verification

```bash
# Check syntax
python -m py_compile backend/app/api/routes/analytics_routes.py

# Frontend check
cd frontend && npx biome check src/api/analytics.js
```

## Related Issues
This fix is part of the broader reliability improvement for analytics endpoints, addressing:
- ROOT-CHAOS-005: Analytics summary graceful degradation
- ROOT-CHAOS-007: Cascading failure prevention
- ROOT-CHAOS-008: Error isolation
- ROOT-CHAOS-009: Recovery path gaps