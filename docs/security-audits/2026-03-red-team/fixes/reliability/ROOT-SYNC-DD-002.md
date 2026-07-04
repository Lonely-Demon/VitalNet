# ROOT-SYNC-DD-002: Multi-tab Coordination Issues

## Unit Details
- **Unit ID**: ROOT-SYNC-DD-002
- **Priority**: P1 HIGH
- **Title**: Multi-tab coordination issues, partial sync handling
- **Source IDs**: SYNC-DD-002, UX-OFFLINE-R3-001, UX-OFFLINE-R3-005
- **Location**: `frontend/src/stores/syncStore.js`
- **Combined Fix**: true (includes linked R3 extensions)

## Issue Description
Multiple tabs in the same browser could simultaneously attempt to sync the same offline queue items, leading to:
- Duplicate submissions to the server
- Race conditions in queue processing
- Unnecessary network traffic
- Potential data inconsistencies

This was a HIGH severity reliability issue affecting users with multiple tabs open.

## Root Cause
The `processQueue()` function in `syncStore.js` had no mechanism to coordinate between tabs. Each tab would independently attempt to process the queue when triggered by online events or page load, with no awareness of other tabs' sync operations.

## Fix Implementation

### 1. BroadcastChannel for Cross-Tab Communication
- Created a `BroadcastChannel` named `vitalnet-sync-coordinator` for real-time communication between tabs
- Handles four message types:
  - `REQUEST_LOCK`: A tab requests the sync lock
  - `LOCK_ACQUIRED`: Notification that a tab acquired the lock
  - `LOCK_RELEASED`: Notification that a tab released the lock
  - `SYNC_COMPLETE`: Notification that sync finished (for UI refresh)

### 2. localStorage Lock Mechanism
- Uses `localStorage` with a `vitalnet_sync_lock` key to track lock state
- Lock contains: `{ tabId: string, timestamp: number }`
- Lock timeout: 30 seconds (prevents stale locks from crashed tabs)
- Fallback for browsers without BroadcastChannel support

### 3. Lock Acquisition Logic
- Before processing, a tab attempts to acquire the sync lock
- If lock is held by another tab (and not expired), the tab skips sync
- If lock is expired or held by the same tab, it can be reacquired
- Lock is automatically released on:
  - Successful sync completion
  - Sync error
  - Page unload (`beforeunload` event)

### 4. Observability
- Added console logging for all coordination events
- Dispatched custom event `vitalnet-queue-synced-by-other-tab` when another tab completes sync
- Added `skipped: true` to return value when sync is skipped due to lock

### 5. Exported Cleanup Function
- Added `cleanupSyncChannel()` export for proper resource cleanup
- Can be called by components on unmount

## Code Changes

### File: `frontend/src/stores/syncStore.js`

```javascript
// Multi-tab coordination constants
const SYNC_CHANNEL_NAME = 'vitalnet-sync-coordinator'
const LOCK_KEY = 'vitalnet_sync_lock'
const LOCK_TIMEOUT_MS = 30000

// Lock acquisition in processQueue()
if (!acquireSyncLock()) {
  console.log('[VitalNet] Sync: Another tab is currently syncing, skipping this attempt')
  requestSyncLock()
  return { synced: 0, failed: 0, skipped: true }
}

// Lock release in finally block
finally {
  releaseSyncLock()
  queueDrainPromise = null
}
```

## Alternative Approaches Considered

1. **Using localStorage events only**: Rejected - less efficient than BroadcastChannel for real-time coordination

2. **Using a shared worker**: Rejected - adds complexity and requires additional file

3. **Using IndexedDB locks**: Rejected - more complex API, no real advantage over localStorage

4. **Server-side coordination**: Rejected - doesn't solve client-side duplicate processing before server contact

## Why This Fix Was Chosen

1. **BroadcastChannel**: Modern, efficient, built-in browser API for cross-tab communication
2. **localStorage fallback**: Ensures compatibility with older browsers
3. **Lock timeout**: Prevents stale locks from crashed tabs blocking sync indefinitely
4. **Minimal changes**: Only modifies syncStore.js, no changes to other components needed
5. **Observability**: Rich logging for debugging multi-tab scenarios

## Files Modified

1. **`frontend/src/stores/syncStore.js`**
   - Added BroadcastChannel initialization and message handling
   - Added localStorage lock functions (acquire, release, request)
   - Modified `processQueue()` to acquire lock before processing
   - Added lock release in finally block
   - Added `cleanupSyncChannel()` export
   - Added observability events and logging

## Validation Steps

1. **Verify syntax**:
   ```bash
   cd frontend && npx @biomejs/biome lint src/stores/syncStore.js
   ```

2. **Test multi-tab coordination**:
   - Open the app in two browser tabs
   - Add items to the offline queue in one tab
   - Force online event or trigger sync
   - Verify only one tab processes the queue (check console logs)
   - Verify the other tab logs "Another tab is currently syncing"

3. **Test lock timeout**:
   - Simulate a tab crash (close without releasing lock)
   - Wait 30+ seconds
   - Verify another tab can acquire the lock

4. **Test fallback**:
   - Test in a browser without BroadcastChannel support
   - Verify localStorage lock still works

## Status

**COMPLETED** - 2026-04-01