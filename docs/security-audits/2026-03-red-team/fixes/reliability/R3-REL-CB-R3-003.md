# Fix Log: R3-REL-CB-R3-003

## Unit Details
- **Unit ID**: R3-REL-CB-R3-003
- **Priority**: P2 MEDIUM
- **Title**: Realtime Case Streams Have No Subscription Bulkhead
- **Source IDs**: REL-CB-R3-003
- **Location**: `frontend/src/hooks/useRealtimeCases.js:18`
- **Combined Fix**: false

## Issue Description
Each mount of the `useRealtimeCases` hook created a unique channel name using `Date.now()`:
```javascript
const channelName = `case_records_${facilityId ?? 'all'}_${userId ?? 'all'}_${Date.now()}`
```

This caused multiple problems:
1. Opening Dashboard, Analytics, and ASHA views together created separate websocket subscriptions
2. Multiple tabs multiplied the fan-out
3. A busy facility could exhaust realtime capacity
4. Live updates would degrade across unrelated screens

## Root Cause
The channel name included `Date.now()` which made it unique for each hook instance, preventing subscription sharing. There was no centralized registry to track and reuse subscriptions.

## Fix Implementation

### Changes Made to `frontend/src/hooks/useRealtimeCases.js`:

1. **Created a centralized subscription registry**:
   - Map-based registry to track active subscriptions
   - Key: deterministic channel name (without timestamp)
   - Value: channel object, callbacks Set, reference count

2. **Implemented bulkhead pattern**:
   - Added `MAX_CONCURRENT_CHANNELS = 5` limit
   - When limit reached, returns null channel
   - Consumer can fall back to polling

3. **Shared subscription with reference counting**:
   - Same filter combination reuses existing channel
   - Callbacks are added to a Set (deduplicated)
   - Reference count tracks when to cleanup

4. **Removed Date.now() from channel name**:
   - Channel name is now deterministic: `case_records_{facilityId}_{userId}`
   - Same filters = same channel

### Code Changes:
```javascript
// Registry to track active subscriptions
const subscriptionRegistry = new Map()
const MAX_CONCURRENT_CHANNELS = 5
let totalChannelCount = 0

// Get or create shared channel
function getOrCreateChannel(facilityId, userId, onInsert, onUpdate) {
  const channelName = `case_records_${facilityId ?? 'all'}_${userId ?? 'all'}`  // No Date.now()!

  if (subscriptionRegistry.has(channelName)) {
    // Reuse existing channel, add callbacks
    const entry = subscriptionRegistry.get(channelName)
    entry.callbacks.onInsert.add(onInsert)
    entry.callbacks.onUpdate.add(onUpdate)
    entry.refCount++
    return entry.channel
  }

  // Check bulkhead limit
  if (totalChannelCount >= MAX_CONCURRENT_CHANNELS) {
    console.warn('[VitalNet] Realtime bulkhead limit reached...')
    return null
  }

  // Create new channel...
}
```

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. Use a single global channel for all cases - Too coarse-grained, loses filtering
2. Implement at the App level with context - More invasive, affects many components
3. Use Supabase's built-in multiplexing - Not available in the client SDK

**Chosen approach:**
- Centralized registry with reference counting
- Bulkhead limit prevents exhaustion
- Minimal changes to existing hook API
- Backward compatible - returns channel ref for external control

This implements the bulkhead pattern: limit concurrent connections while allowing sharing for identical filter combinations.

## Files Changed
- `frontend/src/hooks/useRealtimeCases.js` - Complete rewrite with shared registry

## Verification
- Frontend builds: `cd frontend && npm run build`
- Multiple components using same filters will share one websocket connection
- When limit reached, console warning appears and null channel returned