# Fix Log: R3-REL-OBS-R3-002

## Unit Details
- **Unit ID**: R3-REL-OBS-R3-002
- **Priority**: P1 HIGH
- **Title**: Realtime subscription failures are invisible
- **Source IDs**: REL-OBS-R3-002
- **Location**: `frontend/src/hooks/useRealtimeCases.js:21`
- **Combined Fix**: false

## Issue Description
Realtime subscription failures were invisible to both users and developers. When the Supabase Realtime connection failed, reconnected, or encountered errors, there was no user-facing notification and console logging used inconsistent prefixes. This made debugging production issues difficult and left users unaware when live updates were unavailable.

## Root Cause
The hook had basic reconnection logic but lacked:
1. User-facing notifications for subscription failures
2. Consistent `[REALTIME]` prefix for all console logs (was using `[Realtime]`)
3. Logging for intermediate states like CONNECTING
4. System event handlers for disconnect/reconnect events
5. Failure count tracking in logs

## Fix Implementation

### 1. Added Toast Notifications
- Imported `useToast` from `ToastProvider`
- Added warning toast on first subscription failure: "Live updates temporarily unavailable. Reconnecting..."
- Added error toast when max reconnection attempts exceeded: "Live updates unavailable. Please refresh the page."

### 2. Standardized Console Logging
- Changed `[Realtime]` prefix to `[REALTIME]` for consistency
- Added logging for CONNECTING state
- Added `failureCount` to SUBSCRIPTION_ERROR logs

### 3. Added System Event Handlers
- Added `on('system', { event: 'disconnect' })` handler to log system disconnects
- Added `on('system', { event: 'reconnect' })` handler to log system reconnects
- Both handlers update subscription status and trigger appropriate retry logic

### 4. Enhanced Reconnection Manager
- Added `onMaxAttemptsExceeded` callback parameter
- Called when max reconnection attempts are exceeded
- Triggers user-facing error toast

## Code Changes

### File: `frontend/src/hooks/useRealtimeCases.js`

```javascript
// Added toast import
import { useToast } from '../components/ToastProvider'

// Changed log prefix
console.log(`[REALTIME] ${event}`, { ... })

// Added system event handlers
.on('system', { event: 'disconnect' }, () => {
  logReconnectionEvent('SYSTEM_DISCONNECT', { channelName })
  setSubscriptionStatus('disconnected')
  reconnectManagerRef.current?.scheduleRetry()
})
.on('system', { event: 'reconnect' }, () => {
  logReconnectionEvent('SYSTEM_RECONNECT', { channelName })
  setSubscriptionStatus('connecting')
})

// Added first failure toast notification
if (reconnectionMetrics.failures === 1) {
  toastRef.current?.('Live updates temporarily unavailable. Reconnecting...', 'warning')
}

// Added CONNECTING state logging
} else if (status === 'CONNECTING') {
  setSubscriptionStatus('connecting')
  logReconnectionEvent('CONNECTING', { channelName })
}

// Added failure count to error logs
logReconnectionEvent('SUBSCRIPTION_ERROR', {
  status,
  error: err?.message,
  channelName,
  failureCount: reconnectionMetrics.failures,
})
```

## Alternative Approaches Considered

1. **Redirect to error page on failure**: Rejected - too disruptive, reconnection may succeed
2. **Disable realtime entirely on failure**: Rejected - temporary failures are recoverable
3. **Show modal instead of toast**: Rejected - toasts are less intrusive for transient issues
4. **Add retry button in toast**: Rejected - user can refresh, simpler UX

## Why This Fix Was Chosen

1. **Non-disruptive**: Toasts inform without blocking user workflow
2. **Progressive disclosure**: Warning first, error only on persistent failure
3. **Observable**: Comprehensive console logging for production debugging
4. **Minimal changes**: Added observability without changing core subscription logic
5. **Consistent**: Uses existing toast system and logging patterns

## Files Modified

1. **`frontend/src/hooks/useRealtimeCases.js`**
   - Added `useToast` import
   - Changed `[Realtime]` to `[REALTIME]` in log prefix
   - Added system disconnect/reconnect event handlers
   - Added warning toast on first failure
   - Added error toast on max attempts exceeded
   - Added CONNECTING state logging
   - Added failureCount to error logs

## Validation Steps

1. **Verify syntax**:
   ```bash
   cd frontend && npx @biomejs/biome lint src/hooks/useRealtimeCases.js
   ```

2. **Test error handling**:
   - Simulate network disconnect
   - Verify warning toast appears on first failure
   - Verify console shows `[REALTIME]` prefixed logs
   - Verify error toast appears after max retries

3. **Test recovery**:
   - Verify subscription reconnects when network returns
   - Verify logs show SYSTEM_RECONNECT event

## Observability

Added/Enhanced console logging with `[REALTIME]` prefix:
- `SUBSCRIBED` - successful subscription
- `SUBSCRIPTION_ERROR` - with failure count
- `CHANNEL_CLOSED` - channel closed
- `CONNECTING` - connecting state
- `SYSTEM_DISCONNECT` - system-level disconnect
- `SYSTEM_RECONNECT` - system-level reconnect
- `MAX_ATTEMPTS_EXCEEDED` - persistent failure
- `RETRY_SCHEDULED` - with attempt count and delay
- `BROWSER_ONLINE/OFFLINE` - network state changes

## Status

**COMPLETED** - 2026-04-01
