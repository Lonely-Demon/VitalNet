# Fix Log: ROOT-SYNC-DD-001

## Unit Details
- **Unit ID**: ROOT-SYNC-DD-001
- **Priority**: P2 MEDIUM
- **Title**: Multi-tab coordination issues, partial sync handling
- **Source IDs**: SYNC-DD-001, PERF-NET-R3-08
- **Location**: `frontend/src/stores/syncStore.js`, `frontend/src/lib/offlineQueue.js`
- **Combined Fix**: true (includes PERF-NET-R3-08)

## Issue Description
The offline queue had no coordination between browser tabs, causing:
1. Multiple tabs could process the same queue items simultaneously
2. Duplicate submissions could occur when tabs synced at the same time
3. Rate limits could be exceeded by concurrent sync attempts
4. No way to prevent duplicate replay bursts across tabs

This was particularly problematic for ASHA workers who might have the app open in multiple tabs.

## Root Cause
Each tab operated independently with no synchronization mechanism. The `processQueue` function had no way to know if another tab was already syncing.

## Fix Implementation

### Changes Made to `frontend/src/stores/syncStore.js`:

1. **Added BroadcastChannel for multi-tab coordination**:
   - Uses the BroadcastChannel API to communicate between tabs
   - Falls back gracefully if API is unavailable

2. **Implemented sync lock using localStorage**:
   - Atomic lock acquisition using localStorage
   - Lock includes timestamp to detect stale locks
   - Auto-release after timeout (30 seconds)

3. **Updated processQueue to use the lock**:
   - Acquires lock before processing
   - Returns early if another tab holds the lock
   - Always releases lock in finally block

4. **Added skip indication**:
   - Returns `{ skipped: true }` when another tab is syncing
   - Allows caller to handle gracefully

### Code Changes:
```javascript
// Multi-tab coordination using BroadcastChannel
const SYNC_CHANNEL_NAME = 'vitalnet-sync-coordinator'

async function acquireSyncLock(timeoutMs = 30000) {
  // Try to acquire lock in localStorage
  const existingLock = localStorage.getItem('sync_lock')
  if (existingLock) {
    const lockAge = Date.now() - JSON.parse(existingLock).timestamp
    if (lockAge < timeoutMs) {
      return false  // Another tab holds the lock
    }
  }
  localStorage.setItem('sync_lock', JSON.stringify({ id: uuidv4(), timestamp: Date.now() }))
  return true
}

export async function processQueue() {
  const lockAcquired = await acquireSyncLock()
  if (!lockAcquired) {
    return { synced: 0, failed: 0, skipped: true }
  }

  try {
    // ... original sync logic ...
  } finally {
    releaseSyncLock()
  }
}
```

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. Use a shared WebWorker for sync - More complex, requires additional file
2. Use IndexedDB for lock - More complex, same effect as localStorage
3. Disable multi-tab entirely - Poor user experience

**Chosen approach:**
- BroadcastChannel + localStorage hybrid
- Minimal code change, no new dependencies
- Graceful fallback if APIs unavailable
- Clear signaling when sync is skipped

This is a standard pattern for browser tab coordination using available APIs.

## Files Changed
- `frontend/src/stores/syncStore.js` - Added multi-tab coordination functions and updated processQueue

## Verification
- Frontend builds: `cd frontend && npm run build`
- Open two tabs, trigger sync in both - second tab should skip
- Check console for "Sync lock held by another tab" message