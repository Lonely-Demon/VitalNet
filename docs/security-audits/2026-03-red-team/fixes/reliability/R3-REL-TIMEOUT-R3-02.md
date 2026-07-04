# Fix Log: R3-REL-TIMEOUT-R3-02

## Unit Details
- **Unit ID**: R3-REL-TIMEOUT-R3-02
- **Priority**: P1 HIGH
- **Title**: Offline queue replays can run concurrently and duplicate expensive submissions
- **Source IDs**: REL-TIMEOUT-R3-02
- **Location**: `frontend/src/panels/ASHAPanel.jsx:31`, `frontend/src/stores/syncStore.js`
- **Combined Fix**: false

## Issue Description
When the application loads while coming online, the offline queue can be processed multiple times concurrently:
1. First trigger: `processQueue()` called in `useEffect` on component mount
2. Second trigger: `online` event fires immediately when page loads while online

This could lead to duplicate submissions of expensive case data to the server.

## Root Cause
The `processQueue()` function in `syncStore.js` had a `queueDrainPromise` check to prevent concurrent processing, but there was a race condition:
- The check `if (queueDrainPromise)` happens before the promise is assigned
- If two calls happen in quick succession (mount + online event), both could pass the check before either sets the promise

## Relationship to ROOT-SYNC-DD-002

**ROOT-SYNC-DD-002** addressed multi-tab coordination using BroadcastChannel + localStorage locks. However, it did NOT address concurrent processing within the same tab.

This fix (R3-REL-TIMEOUT-R3-02) complements ROOT-SYNC-DD-002 by adding same-tab protection.

## Fix Implementation

### 1. Added Processing Flag
Added an `isProcessingQueue` boolean flag that is set immediately at the start of `processQueue()`:

```javascript
let isProcessingQueue = false // R3-REL-TIMEOUT-R3-02: Prevent concurrent same-tab processing
```

### 2. Early Flag Check
The flag is checked BEFORE the `queueDrainPromise` check to prevent race conditions:

```javascript
export async function processQueue() {
  // R3-REL-TIMEOUT-R3-02: Prevent concurrent same-tab queue processing
  // This addresses the issue where mount + online event can trigger concurrent replays
  if (isProcessingQueue) {
    console.log('[VitalNet] Sync: Already processing queue in this tab, skipping duplicate call')
    if (queueDrainPromise) {
      return queueDrainPromise
    }
    return { synced: 0, failed: 0, skipped: true }
  }

  if (queueDrainPromise) {
    return queueDrainPromise
  }

  // Mark as processing immediately to prevent race conditions
  isProcessingQueue = true
  // ... rest of function
}
```

### 3. Flag Reset in Finally Block
The flag is reset in the `finally` block to ensure it's always reset, even on errors:

```javascript
try {
    return await queueDrainPromise
  } finally {
    // Always release the lock when done (success or failure)
    releaseSyncLock()
    queueDrainPromise = null
    // R3-REL-TIMEOUT-R3-02: Reset processing flag
    isProcessingQueue = false
  }
```

### 4. Flag Reset on Lock Failure
Also reset the flag if the multi-tab lock cannot be acquired:

```javascript
if (!acquireSyncLock()) {
    console.log('[VitalNet] Sync: Another tab is currently syncing, skipping this attempt')
    requestSyncLock()
    isProcessingQueue = false  // Reset flag here too
    return { synced: 0, failed: 0, skipped: true }
  }
```

## Code Changes

### File: `frontend/src/stores/syncStore.js`

```javascript
// Added flag at module level
let isProcessingQueue = false // R3-REL-TIMEOUT-R3-02: Prevent concurrent same-tab processing

// In processQueue function:
export async function processQueue() {
  // R3-REL-TIMEOUT-R3-02: Prevent concurrent same-tab queue processing
  // This addresses the issue where mount + online event can trigger concurrent replays
  if (isProcessingQueue) {
    console.log('[VitalNet] Sync: Already processing queue in this tab, skipping duplicate call')
    if (queueDrainPromise) {
      return queueDrainPromise
    }
    return { synced: 0, failed: 0, skipped: true }
  }

  if (queueDrainPromise) {
    return queueDrainPromise
  }

  // Mark as processing immediately to prevent race conditions
  isProcessingQueue = true

  // ROOT-SYNC-DD-002: Acquire sync lock before processing
  if (!acquireSyncLock()) {
    console.log('[VitalNet] Sync: Another tab is currently syncing, skipping this attempt')
    requestSyncLock()
    isProcessingQueue = false  // Reset flag on lock failure
    return { synced: 0, failed: 0, skipped: true }
  }

  // ... rest of function

  try {
    return await queueDrainPromise
  } finally {
    releaseSyncLock()
    queueDrainPromise = null
    isProcessingQueue = false  // Reset flag in finally block
  }
}
```

## Alternative Approaches Considered

1. **Debouncing the online event**: Rejected - adds complexity and delays necessary syncs
2. **Removing mount-time processQueue call**: Rejected - users expect offline items to sync on app load
3. **Using a mutex library**: Rejected - overkill for this use case, adds dependency
4. **Server-side deduplication**: Rejected - doesn't prevent unnecessary network calls

## Why This Fix Was Chosen

1. **Simple**: Single boolean flag, minimal code changes
2. **Effective**: Immediately prevents race condition at function entry
3. **Defensive**: Flag reset in both success and failure paths
4. **Complementary**: Works alongside ROOT-SYNC-DD-002 multi-tab coordination
5. **Observable**: Logs when duplicate calls are skipped

## Files Modified

1. **`frontend/src/stores/syncStore.js`**
   - Added `isProcessingQueue` boolean flag
   - Added early flag check at function entry
   - Added flag reset on lock acquisition failure
   - Added flag reset in finally block

## Validation Steps

1. **Verify syntax**:
   ```bash
   cd frontend && npx @biomejs/biome lint src/stores/syncStore.js
   ```

2. **Test concurrent same-tab processing**:
   - Open browser DevTools
   - Add items to offline queue
   - Simulate online condition while page loads
   - Verify only one sync attempt occurs (check console logs)
   - Verify log message: "Already processing queue in this tab, skipping duplicate call"

3. **Test multi-tab coordination** (ROOT-SYNC-DD-002):
   - Open app in two tabs
   - Add items to offline queue in one tab
   - Trigger sync in both tabs
   - Verify only one tab processes the queue

4. **Test error recovery**:
   - Simulate a sync error
   - Verify flag is properly reset
   - Verify subsequent sync attempts work

## Observability

Added console logging:
- `[VitalNet] Sync: Already processing queue in this tab, skipping duplicate call` - when concurrent call is detected
- `[VitalNet] Sync: Another tab is currently syncing, skipping this attempt` - when multi-tab lock is held (existing)

## Status

**COMPLETED** - 2026-04-01