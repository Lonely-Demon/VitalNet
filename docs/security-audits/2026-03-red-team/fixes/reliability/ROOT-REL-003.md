# Fix Log: ROOT-REL-003

## Issue Solved
Retry logic was missing on all API calls in the frontend. The existing implementation in `cases.js` had flawed retry logic that would retry on ALL errors, including 4xx client errors (which should never be retried). Additionally, `analytics.js` and `admin.js` had no retry logic at all.

**Source ID**: REL-003

## Fix Applied
Created a centralized retry utility (`frontend/src/api/retry.js`) with the following features:

1. **Exponential backoff with jitter**: Retries with increasing delays (500ms, 1000ms, 2000ms) plus random jitter (±25%) to prevent thundering herd problems.

2. **Smart retry conditions**: Only retries on:
   - Network errors (no response)
   - 5xx server errors
   - 429 Too Many Requests
   - 408 Request Timeout

3. **No retry on 4xx client errors**: Client errors (400-499) are not retried as they indicate invalid requests that will fail again.

4. **Observability logging**: All retry attempts are logged with timestamps, URL, attempt number, status code, and error message.

5. **Timeout support**: Built-in timeout handling with AbortController.

Updated the following API files to use the new retry utility:
- `frontend/src/api/cases.js` - Replaced flawed retry logic with centralized utility
- `frontend/src/api/analytics.js` - Added retry logic (was missing entirely)
- `frontend/src/api/admin.js` - Added retry logic (was missing entirely)

## Why This Fix Was Chosen
- **Centralized**: Single retry implementation ensures consistent behavior across all API calls
- **Idempotent-safe**: Does not retry on 4xx errors, preventing duplicate operations
- **Production-ready**: Includes exponential backoff with jitter to prevent cascading failures
- **Observable**: Logs all retry attempts for debugging and monitoring
- **Minimal changes**: Reuses existing timeout constants and follows existing code patterns

## Files Changed
- `frontend/src/api/retry.js` - NEW: Centralized retry utility
- `frontend/src/api/cases.js` - Updated to use retry utility
- `frontend/src/api/analytics.js` - Updated to use retry utility
- `frontend/src/api/admin.js` - Updated to use retry utility

## Verification
1. Run the frontend dev server: `cd frontend && npm run dev`
2. Test API calls - verify that:
   - Network failures trigger retries with exponential backoff
   - 5xx errors trigger retries
   - 4xx errors do NOT trigger retries (check console for retry logs)
   - Retry attempts are logged to console with `[RETRY]` prefix
3. Check browser console for retry logs during normal operation and error scenarios