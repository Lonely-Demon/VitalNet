# Fix Log: ROOT-SYNC-DD-003 - Silent data loss on 4xx server errors

## Unit Information
- **Unit ID**: ROOT-SYNC-DD-003
- **Type**: root_bundle (combined fix)
- **Priority**: P1 (HIGH)
- **Domain**: reliability
- **Source IDs**: SYNC-DD-003, DATA-MIGRATE-R3-005

## Issue Description
Combined bundle addressing two related issues:
1. **SYNC-DD-003**: Silent data loss on 4xx server errors - queue items were deleted without user notification
2. **DATA-MIGRATE-R3-005**: Schema-rollout mismatch can permanently drop offline cases

## Root Cause
In `frontend/src/stores/syncStore.js` (lines 133-142), when processing the offline queue and encountering a 4xx HTTP error:
- The code would `dequeue()` (delete) the item from the queue
- Log a warning to console (not visible to users)
- Increment the failed counter but provide no way to recover the data

This meant permanent client errors (e.g., validation errors, unauthorized, not found) would silently lose user data without any notification.

## Fix Applied

### 1. Failed Submissions Store (offlineQueue.js)
Added a new IndexedDB store `failed_submissions` to preserve failed items:
- Upgraded database from version 2 to 3
- Created `failed_submissions` object store with indexes for `failed_at` and `original_error`
- Added metadata: `failed_at`, `original_error`, `retry_count`, `last_retry_at`

### 2. Failed Queue Functions (offlineQueue.js)
Added new exported functions:
- `moveToFailedQueue(clientId, originalError)` - Moves item from main queue to failed queue
- `getAllFailed()` - Returns all failed submissions for manual review
- `getFailedCount()` - Returns count of failed items
- `removeFailed(clientId)` - Removes item after manual resolution
- `retryFailed(clientId)` - Moves failed item back to main queue for retry

### 3. Updated Queue Processing (syncStore.js)
Modified `processQueue()` to use the new failed queue:
- Changed 4xx error handling from `dequeue()` to `moveToFailedQueue()`
- Preserves original error message for debugging
- Enhanced logging with `console.error` instead of `console.warn`
- Updated sync completion event to include `failedQueueCount`

### 4. User Notification
The sync completion event now includes `failedQueueCount` allowing UI to:
- Display count of items requiring manual review
- Show appropriate messaging to users
- Enable recovery workflows

## Files Changed
- `frontend/src/lib/offlineQueue.js` - Added failed submissions store and management functions
- `frontend/src/stores/syncStore.js` - Updated 4xx error handling to use failed queue

## Why This Fix
**Failed queue pattern chosen because**:
- Industry-standard solution for handling permanent failures
- Preserves data for debugging and manual review
- Allows retry mechanism for transient issues that were misclassified
- No data loss - users can see what failed and why

**Alternative considered**: Simply not dequeuing on 4xx errors
- Rejected: Would cause head-of-line blocking - subsequent valid items would never sync
- Our approach: Move to separate store, continue processing queue

**Alternative considered**: Immediate rethrow to user
- Rejected: Queue processing happens in background; user may not be aware
- Our approach: Background move to failed queue + event notification for UI

## Tests/Validation
- Verified database upgrade from v2 to v3 creates failed_submissions store
- Confirmed moveToFailedQueue preserves payload and adds metadata
- Tested retryFailed moves item back to main queue with incremented retry_count
- Validated getAllFailed returns items sorted by failed_at
- Confirmed console logging shows error details for observability

## Remaining Risk
**Low Risk**: 
- Failed queue could grow large if never cleaned up
- No automatic cleanup mechanism (intentional - requires manual review)

**Mitigation**:
- UI can implement cleanup via `removeFailed()` after manual review
- Retry mechanism available via `retryFailed()` for items that were incorrectly classified as 4xx
- Event notifications enable UI to show failed queue count

**Future Enhancement**:
- Add UI component to view/retry/remove failed submissions
- Add automatic cleanup of old failed items after N days
- Add metrics/alerting on failed queue growth