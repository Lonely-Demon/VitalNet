# Fix Log: ROOT-REL-005

## Issue Solved
Sync failures were silently swallowed - users had no visibility into when their offline submissions failed to sync. The original implementation had three critical issues:

1. **No logging for transient errors**: Server errors (500, 503, etc.) were silently counted as failures without any console output
2. **No logging for network errors**: Network failures during sync were silently swallowed
3. **No user notification**: When sync failures occurred, users received no feedback - they didn't know their submissions hadn't been synced

**Source IDs**: REL-005, REL-OBS-R3-004, REL-RECOVER-R3-003, REL-RECOVER-R3-004, UX-OFFLINE-R3-002, QA-E2E-R3-001

## Fix Applied

1. **Added logging for transient errors** (500, 503, etc.):
   - Uses `console.error` to log when a transient server error occurs during sync
   - Includes the client_id and HTTP status code for debugging

2. **Added logging for network errors**:
   - Uses `console.error` to log when a network error occurs during sync
   - Includes the client_id and error message for debugging

3. **Added custom event for observability**:
   - Dispatches `vitalnet-sync-failed` custom event when failures occur
   - Event detail includes `failed`, `synced`, and `total` counts
   - Allows other components to react to sync failures (e.g., for monitoring/alerting)

4. **Added user notification in ASHAPanel**:
   - Shows error toast when `result.failed > 0` on initial sync
   - Shows error toast when `result.failed > 0` on online event handler
   - Message clearly indicates failures and that retries will happen automatically

## Why This Fix Was Chosen

- **Minimal changes**: The fix follows existing code patterns and doesn't require changes to other parts of the system
- **Non-breaking**: Users continue to receive the same behavior (automatic retry) but now have visibility
- **Observable**: Console logging and custom events enable debugging and monitoring
- **User-friendly**: Error toasts inform users of failures without disrupting their workflow
- **Consistent**: Follows the same pattern as success notifications (synced count)

## Files Changed
- `frontend/src/stores/syncStore.js` - Added logging for transient/network errors and custom event dispatch
- `frontend/src/panels/ASHAPanel.jsx` - Added user notification for sync failures

## Verification
1. Run the frontend dev server: `cd frontend && npm run dev`
2. Open browser console
3. Test sync failure scenarios:
   - Go offline, submit a case (queued)
   - Keep offline, trigger sync (should see network error in console)
   - Come online with a mock server that returns 500 errors (should see transient error in console)
4. Verify toast notifications appear when failures occur
5. Verify `vitalnet-sync-failed` event is dispatched (check console for custom event or add listener)