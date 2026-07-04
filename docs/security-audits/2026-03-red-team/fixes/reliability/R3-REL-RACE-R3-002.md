# R3-REL-RACE-R3-002: Realtime Update Race Condition

## Issue Summary
**Title**: Realtime Update Can Be Lost Before Initial History Load Completes  
**Priority**: P1 HIGH  
**Type**: Race Condition  
**Location**: `frontend/src/panels/ASHAPanel.jsx:57`

## Problem Description
The ASHAPanel had a race condition where realtime updates could be lost or cause errors before the initial history load completed. When a user clicked on the "history" tab:

1. `fetchSubmissions()` started loading history (async)
2. `useRealtimeCases` hook started listening for realtime updates immediately
3. If a realtime update arrived BEFORE `fetchSubmissions()` completed, the `onUpdate` callback would:
   - Try to update a submission that might not exist in the state yet
   - Cause potential errors or silent failures

### Race Condition Scenario
1. User clicks "history" tab
2. `fetchSubmissions()` starts - loading = true, submissions = []
3. `useRealtimeCases` starts subscribing (enabled = true)
4. Backend processes an offline submission → sends realtime UPDATE event
5. `onUpdate` callback fires → tries to map over empty submissions array
6. The update is for a case that doesn't exist in the local state yet
7. Either the update is lost, or if it does exist but with stale data, it gets incorrect data

## Fix Applied
1. **Added historyReady state**: New state variable `historyReady` tracks when history has been loaded
2. **Sequenced realtime subscription**: Realtime updates are only enabled AFTER history is loaded
3. **Added defensive check in onUpdate**: Even with the enabled flag, added a runtime check to ignore updates when history is not ready
4. **Reset flag on fetch start**: Reset `historyReady` to false at the start of each fetch to prevent stale updates
5. **Added useCallback**: Wrapped `fetchSubmissions` in `useCallback` to satisfy React's exhaustive dependency rule
6. **Added observability**: Added debug logging for when history loads and when realtime updates are ignored

### Code Changes
- Added `historyReady` state variable (line 28)
- Added `useCallback` import
- Wrapped `fetchSubmissions` in `useCallback`
- Modified `useRealtimeCases` enabled prop to include `historyReady` check
- Added defensive check in `onUpdate` callback
- Added debug logging

## Why This Fix Over Alternatives
**Alternative 1: Queue realtime updates until history loads**  
Rejected: More complex to implement; requires additional queue state management.

**Alternative 2: Disable realtime until explicit user action**  
Rejected: Poor user experience; users expect to see updates in real-time.

**Chosen approach**: Simple state flag approach that ensures proper sequencing. The `historyReady` flag acts as a gate that only opens after history is loaded, preventing any race condition. The dual protection (enabled flag + runtime check) provides defense in depth.

## Files Changed
- `frontend/src/panels/ASHAPanel.jsx`

## Verification
```bash
# Run linter to verify no issues
npx @biomejs/biome lint frontend/src/panels/ASHAPanel.jsx

# Expected: No errors
```

## Observability
The fix adds the following logging:
- `[ASHAPanel] History loaded, realtime updates now active` - When history fetch completes (includes count)
- `[ASHAPanel] Ignoring realtime update - history not yet loaded` - When a realtime update arrives before history is ready (includes caseId)

## Technical Details
The fix uses a two-layer protection approach:

1. **Enable flag layer**: `enabled: activeTab === 'history' && historyReady`
   - The Supabase realtime subscription is only established when historyReady is true
   - This prevents the subscription from even receiving events before history is ready

2. **Runtime check layer**: The `onUpdate` callback checks `historyReady` before processing
   - This provides defense in case the enable flag changes mid-operation
   - Logs debug information when updates are ignored