# Fix Log: ROOT-REL-004

## Issue Solved
IndexedDB queue had no size limit implementation that could lead to storage exhaustion. The original implementation had three critical issues:

1. **No atomic capacity check**: The queue checked capacity before adding, but this was not atomic - multiple tabs could both check and think there's room
2. **No warning when approaching limit**: Users had no advance notice before the queue became full
3. **No eviction policy**: When full, the queue simply rejected new items instead of managing capacity gracefully

**Source IDs**: REL-004, REL-RACE-R3-003, UX-OFFLINE-R3-006

## Fix Applied

1. **Atomic queue operations**: Changed from check-then-put pattern to using IndexedDB transactions for atomic operations. The enqueue function now uses a transaction to ensure the count check and insert are atomic.

2. **FIFO eviction policy**: When the queue reaches capacity, the system now automatically evicts the oldest items (based on `queued_at` timestamp) instead of rejecting new submissions. This ensures:
   - No data loss for users (oldest items are removed, not newest)
   - Continuous operation even when queue is full
   - Predictable behavior under high load

3. **Warning events**: Added a new `offline-queue-warning` custom event that fires when the queue reaches 80% capacity. This allows the UI to display warnings to users before the queue becomes full.

4. **Enhanced notifications**: The `offline-queue-changed` event now includes the current queue count in its detail, making it easier for components to react to queue changes.

### Configuration Constants
- `MAX_QUEUE_SIZE = 50` - Maximum number of items in queue
- `WARNING_THRESHOLD = 0.8` - 80% threshold for warning events
- `EVICTION_BATCH_SIZE = 5` - Number of items to evict when full

## Why This Fix Was Chosen

- **Atomic operations**: Using IndexedDB transactions ensures the capacity check and insert are atomic, preventing race conditions across multiple tabs
- **FIFO eviction**: Oldest items are evicted first, which is the most predictable and fair policy for offline queues
- **Non-breaking**: Instead of throwing an error when full, the queue now gracefully manages capacity, improving user experience
- **Observable**: Warning events allow the UI to inform users about queue status before problems occur
- **Minimal changes**: The fix follows existing code patterns and doesn't require changes to other parts of the system

## Files Changed
- `frontend/src/lib/offlineQueue.js` - Updated with atomic operations, FIFO eviction, and warning events

## Verification
1. Run the frontend dev server: `cd frontend && npm run dev`
2. Open browser console
3. Test queue operations:
   - Add items to the queue and verify the `offline-queue-changed` event fires with count
   - Fill queue to 80% capacity and verify `offline-queue-warning` event fires
   - Fill queue to capacity and verify oldest items are evicted (check console for eviction logs)
4. Test multi-tab scenario: Open two tabs, fill queue in one tab, verify the other tab sees consistent state