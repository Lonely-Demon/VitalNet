# ROOT-CHAOS-007: Frontend Analytics Retry Logic

## Issue Summary
The frontend analytics API calls had no retry logic, meaning transient failures would immediately result in no data display. Users would see empty analytics panels without any indication of what went wrong.

This is a MEDIUM (P2) reliability issue representing "cascading failure risks, recovery path gaps".

## Fix Applied

### Frontend Changes
Enhanced `frontend/src/api/analytics.js` with:

1. **Retry with backoff**: Uses existing `fetchWithRetry` utility with exponential backoff
2. **Timeout handling**: 15-second timeout prevents hanging requests
3. **Graceful fallback**: Returns fallback data structure when all retries fail
4. **Error logging**: Logs errors for observability

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. **Show error to user** - Would require additional UI components
2. **Infinite retry** - Would cause thundering herd issues
3. **Circuit breaker** - Too complex for user-initiated requests

**Chosen approach:**
- Leverages existing retry utility
- Provides fallback data so UI remains functional
- Minimal code changes

## Files Changed

### Frontend
- `frontend/src/api/analytics.js`
  - Added `fetchWithRetry` for both analytics endpoints
  - Added timeout configuration (15s)
  - Added fallback response structures

## Verification

```bash
# Frontend check
cd frontend && npx biome check src/api/analytics.js
```

## Related Issues
This fix addresses:
- ROOT-CHAOS-005: Backend graceful degradation
- ROOT-CHAOS-006: Emergency rate endpoint
- ROOT-CHAOS-008: Error isolation
- ROOT-CHAOS-009: Recovery path gaps