# ROOT-CHAOS-003: No Timeout on Frontend Fetch Calls

## Issue Summary
Frontend fetch calls had no timeout and no AbortController support, causing:
- Hung requests blocking UI
- Memory leaks from abandoned requests
- Poor UX when navigating away
- Resource exhaustion

This was a HIGH (P1) reliability issue affecting all case API endpoints.

## Fix Applied

### 1. Added Timeout Constants
- `TIMEOUT_READ`: 10,000ms (10 seconds) for GET requests
- `TIMEOUT_WRITE`: 30,000ms (30 seconds) for PATCH/POST/PUT requests
- `MAX_RETRIES`: 2 for read operations

### 2. Created AbortController Helper (`createTimeoutController`)
- Creates an AbortController with a setTimeout
- Returns both controller and timeoutId for proper cleanup
- Uses DOMException with 'TimeoutError' name for proper error identification

### 3. Created Reusable Fetch Wrapper (`fetchWithTimeout`)
- Wraps fetch with AbortController signal
- Implements retry logic with exponential backoff for read operations
- Properly clears timeout on success or failure
- Throws AbortError immediately on timeout (no retry)
- Only retries on network errors, not HTTP errors

### 4. Updated All API Functions
- `getCases()`: Uses 10s timeout with retry (read operation)
- `reviewCase()`: Uses 30s timeout without retry (write operation - idempotency concerns)
- `getMySubmissions()`: Uses 10s timeout with retry (read operation)

## Timeout Values Chosen and Rationale

| Operation Type | Timeout | Rationale |
|----------------|---------|-----------|
| GET (reads) | 10s | Case list queries should be fast; allows for pagination |
| PATCH (writes) | 30s | Review operations may involve database writes; more tolerant |
| Retry count | 2 | Provides resilience without excessive delays |

**Why 10s for reads?**
- Case lists are paginated (25 items)
- Should complete quickly for good UX
- 10s is enough for most network conditions

**Why 30s for writes?**
- Review operations may trigger ML inference
- Database writes can take longer
- Write operations are less frequent

**Why no retry for writes?**
- Write operations may not be idempotent
- Prevents duplicate submissions
- User can manually retry if needed

## Files Modified

1. **`frontend/src/api/cases.js`**
   - Added timeout constants (TIMEOUT_READ, TIMEOUT_WRITE, MAX_RETRIES)
   - Added `createTimeoutController()` helper function
   - Added `fetchWithTimeout()` wrapper function
   - Updated `getCases()` to use timeout with retry
   - Updated `reviewCase()` to use timeout without retry
   - Updated `getMySubmissions()` to use timeout with retry

## Alternative Approaches Considered

1. **Using a library like axios**: Rejected - adds dependency, fetch is sufficient
2. **Global fetch wrapper**: Rejected - would require more invasive changes
3. **React Query / SWR**: Rejected - significant architectural change
4. **Component-level AbortController**: Partially implemented - the AbortController is available for component use but not automatically integrated with React lifecycle

## AbortController Integration

The implementation provides AbortController capability through:
1. **Signal-based cancellation**: The fetch signal is connected to AbortController
2. **Timeout-triggered abort**: Automatically aborts after timeout period
3. **External cancellation support**: Components can access the controller pattern for manual cancellation

**Note**: Full integration with React component lifecycle (cleanup on unmount) would require modifying the calling components to pass and manage AbortController instances. The current implementation provides the foundation - components can create their own AbortController and pass its signal to these API functions if needed.

## Remaining Risks

1. **Other API files not covered**: The fix only covers `cases.js`. Other API files (`analytics.js`, `admin.js`) may need similar treatment.

2. **Component-level cancellation**: Components calling these APIs don't automatically cancel on unmount. They would need to:
   - Create their own AbortController
   - Pass its signal to the API call
   - Call abort() in useEffect cleanup

3. **Retry on slow networks**: May delay error reporting on truly failed requests. Consider reducing retries or adding user-configurable options.

4. **Timeout too short for large datasets**: If case lists grow significantly, 10s may not be enough. Monitor and adjust as needed.

## Validation Steps

1. **Verify syntax**:
```bash
node --check frontend/src/api/cases.js
```

2. **Test timeout behavior**:
   - Mock an API that delays responses beyond timeout
   - Verify AbortError is thrown with "Request timeout" message

3. **Test retry behavior**:
   - Mock a network failure
   - Verify retry attempts are made with exponential backoff
   - Verify no retry on successful response

4. **Test write operations**:
   - Verify reviewCase() does not retry on failure
   - Verify 30s timeout is applied

5. **Integration test**:
   - Run the frontend and navigate through case list
   - Verify requests complete successfully under normal conditions
   - Verify timeout errors are handled gracefully with user feedback