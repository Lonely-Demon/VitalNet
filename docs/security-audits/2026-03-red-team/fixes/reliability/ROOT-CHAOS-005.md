# ROOT-CHAOS-005: Analytics Endpoint Graceful Degradation

## Issue Summary
The analytics summary endpoint had no graceful degradation when individual database queries fail. A single query failure would cause the entire endpoint to fail, resulting in no analytics data for the user.

This is a MEDIUM (P2) reliability issue representing "cascading failure risks, recovery path gaps".

## Fix Applied

### Backend Changes
Added graceful degradation to `backend/app/api/routes/analytics_routes.py`:

1. **Query-level try-catch**: Each analytics query now has its own try-catch block
2. **Timeout handling**: Added 10-second timeout for each query using `asyncio.wait_for()`
3. **Partial data return**: When some queries fail, the endpoint returns available data with degradation indicators
4. **Observability**: Failed queries are logged and included in response `_failed_queries` array

### Frontend Changes
Added resilience to `frontend/src/api/analytics.js`:

1. **Retry logic**: Uses `fetchWithRetry` with 2 retries and 15s timeout
2. **Fallback response**: Returns graceful degradation structure when all retries fail
3. **Degradation detection**: Handles `_degraded` and `_fallback` response flags

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. **Circuit breaker** - Too heavy for analytics queries that are user-initiated
2. **Caching** - Would help but doesn't address the root cause of query failures
3. **Background jobs** - Overkill for real-time analytics

**Chosen approach:**
- Individual query isolation with fallback to partial data
- Provides best UX: users see available data even when some queries fail
- Minimal overhead: no new infrastructure needed

## Files Changed

### Backend
- `backend/app/api/routes/analytics_routes.py`
  - Added `QUERY_TIMEOUT_SECONDS = 10` constant
  - Wrapped each query in try-catch with timeout handling
  - Added `_degraded` and `_failed_queries` to response when partial failure occurs

### Frontend
- `frontend/src/api/analytics.js`
  - Added retry logic with `fetchWithRetry`
  - Added timeout handling (15s)
  - Added fallback response structure for graceful degradation

## Verification

### Backend
```bash
# Check syntax
python -m py_compile backend/app/api/routes/analytics_routes.py
```

### Frontend
```bash
# Check syntax
cd frontend && npx biome check src/api/analytics.js
```

### Manual Testing
1. Start backend and frontend
2. Load doctor dashboard
3. Verify analytics summary loads
4. Simulate database timeout (optional: add sleep to query)
5. Verify partial data is returned with `_degraded: true`

## Related Issues
This fix also addresses aspects of:
- ROOT-CHAOS-006: Recovery path gaps
- ROOT-CHAOS-007: Cascading failure risks
- ROOT-CHAOS-008: Error isolation
- ROOT-CHAOS-009: Partial failure handling