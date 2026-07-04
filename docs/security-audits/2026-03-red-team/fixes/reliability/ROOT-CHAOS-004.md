# ROOT-CHAOS-004: Thundering Herd on Reconnection

## Issue Summary
When multiple clients reconnect simultaneously (e.g., after network outage), they all retry immediately, causing:
- Server overload (thundering herd)
- Cascading failures
- Poor UX for all users

This was a HIGH (P1) reliability issue in the `useRealtimeCases` hook.

## Fix Applied

### 1. Added Backoff Configuration Constants
- `initialDelayMs`: 0 (random 0-2s initial delay to spread load)
- `maxInitialDelayMs`: 2000ms
- `baseDelayMs`: 1000ms (exponential base: 2^attempt * 1000ms)
- `maxDelayMs`: 60000ms (cap at 60 seconds)
- `maxAttempts`: 10 (before requiring user action)
- `jitterPercent`: 0.2 (+/- 20% randomness)

### 2. Created Jittered Exponential Backoff Calculator
- Initial connection: random 0-2s delay to spread client load
- Exponential backoff: 2^attempt * 1000ms
- Jitter: +/- 20% randomness to prevent synchronized retries
- Max delay cap: 60 seconds
- Max attempts: 10 before requiring user refresh

### 3. Created Reconnection Manager Hook
- Tracks attempt count with useRef
- Schedules retries with calculated backoff delays
- Clears pending timeouts on cleanup
- Resets attempts on successful connection or component unmount

### 4. Added Subscription Status Handling
- Listens to Supabase subscription status callbacks
- Triggers backoff retry on `CHANNEL_ERROR` or `TIMED_OUT`
- Resets attempt counter on successful `SUBSCRIBED` status

### 5. Added Browser Online/Offline Event Handling
- Listens to `window.online` and `window.offline` events
- Resets retry attempts when browser comes back online
- Prevents double-retry when both browser online event AND Supabase reconnection fire

### 6. Added Observability
- Console logging with timestamps for all reconnection events
- Metrics tracking: attempts, successes, failures, last attempt time/delay
- Exported `getReconnectionMetrics()` for external monitoring

## Backoff Algorithm Chosen and Rationale

**Algorithm**: Jittered Exponential Backoff

```
delay = min(2^attempt * baseDelay * (1 + random(-20%, +20%)), maxDelay)
```

**Why this algorithm:**
1. **Exponential backoff**: Gives server time to recover between retry waves
2. **Jitter**: Prevents multiple clients from synchronizing their retries
3. **Initial random delay**: Spreads initial connection load across time
4. **Max delay cap**: Prevents excessively long wait times (60s max)
5. **Max attempts**: Prevents infinite retry loops, requires user intervention

**Delay progression example:**
| Attempt | Base Delay | With Jitter (range) |
|---------|------------|---------------------|
| 0 (initial) | 0-2000ms | 0-2000ms |
| 1 | 2000ms | 1600-2400ms |
| 2 | 4000ms | 3200-4800ms |
| 3 | 8000ms | 6400-9600ms |
| 4 | 16000ms | 12800-19200ms |
| 5 | 32000ms | 25600-38400ms |
| 6+ | 60000ms | 48000-60000ms (capped) |

## Thundering Herd Prevention

The fix prevents thundering herd in multiple ways:

1. **Initial random delay (0-2s)**: When page loads, each client waits a random time before first connection attempt. This naturally spreads out connection requests.

2. **Jitter on retries**: When reconnection is needed, the +/- 20% jitter ensures clients don't retry at exactly the same time.

3. **Exponential backoff**: Each failed attempt doubles the wait time, reducing the intensity of retry waves.

4. **Browser event coordination**: By listening to `online`/`offline` events and resetting attempts, we prevent duplicate retry attempts from different sources.

5. **Max attempts limit**: After 10 failed attempts, the system stops retrying and requires user action, preventing endless retry storms.

## Files Modified

1. **`frontend/src/hooks/useRealtimeCases.js`**
   - Added BACKOFF_CONFIG constants
   - Added reconnectionMetrics object for observability
   - Added logReconnectionEvent() function
   - Added calculateBackoffDelay() utility function
   - Added useReconnectionManager() hook
   - Modified useRealtimeCases() to use backoff on subscription errors
   - Added browser online/offline event listeners
   - Added getReconnectionMetrics() export

## Alternative Approaches Considered

1. **Using Supabase's built-in reconnection**: Rejected - Supabase's default behavior doesn't have configurable backoff or jitter

2. **Using a library like retry-axios**: Rejected - adds dependency, custom implementation gives more control

3. **Server-side rate limiting**: Rejected - doesn't solve client-side thundering herd problem

4. **Centralized retry coordinator**: Rejected - too complex for this use case, local backoff is sufficient

## Remaining Risks

1. **Multiple tabs**: If user has multiple tabs open, each will have its own backoff timer. This could increase total load but is generally acceptable.

2. **Browser back/forward cache**: Some browsers may restore page state without triggering fresh connections, potentially bypassing the initial delay.

3. **Very large scale deployments**: At very high scale (1000+ simultaneous clients), even jittered backoff may cause issues. Consider server-side connection queuing for such scenarios.

4. **Metrics persistence**: Current metrics are in-memory only and reset on page refresh. For production monitoring, consider sending metrics to an analytics service.

5. **User notification**: After max attempts, user isn't explicitly notified. Consider adding a UI toast or banner.

## Validation Steps

1. **Verify syntax**:
   ```bash
   cd frontend && npm run build
   ```

2. **Test initial delay**:
   - Open browser console
   - Load page with useRealtimeCases
   - Verify "INITIAL_CONNECT_SCHEDULED" log with delayMs

3. **Test backoff on error**:
   - Simulate network failure during subscription
   - Verify "SUBSCRIPTION_ERROR" log
   - Verify "RETRY_SCHEDULED" log with increasing delays
   - Verify delays follow exponential pattern with jitter

4. **Test max attempts**:
   - Keep network failing
   - After 10 attempts, verify "MAX_ATTEMPTS_EXCEEDED" log
   - Verify no more retry attempts

5. **Test browser online event**:
   - Disconnect network, wait for retries
   - Reconnect network
   - Verify "BROWSER_ONLINE" log
   - Verify attempts are reset

6. **Integration test**:
   - Run frontend with backend
   - Verify real-time updates work normally
   - Verify reconnection works after network interruption