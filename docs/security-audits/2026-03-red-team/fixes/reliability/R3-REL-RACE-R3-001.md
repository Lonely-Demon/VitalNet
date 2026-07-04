# R3-REL-RACE-R3-001: Auth Profile Fetch Race Condition

## Issue Summary
**Title**: Auth Profile Fetch Can Overwrite Newer Session State  
**Priority**: P1 HIGH  
**Type**: Race Condition  
**Location**: `frontend/src/store/authStore.jsx:12`

## Problem Description
The authStore.jsx had a critical race condition where profile fetches could overwrite newer session state. The root cause was a duplicate `fetchProfile` function definition - the second function (without race condition handling) was overwriting the first function (with race condition handling using `currentUserIdRef`).

### Race Condition Scenario
1. User logs in → session A created → fetchProfile(A) started
2. User quickly logs out and logs in as different user → session B created → fetchProfile(B) started
3. If fetchProfile(A) completes AFTER fetchProfile(B), the older profile (A) would overwrite the newer profile (B)

## Fix Applied
1. **Removed duplicate function**: Eliminated the second `fetchProfile` function that was overwriting the race-condition-safe version
2. **Enhanced stale response detection**: The existing `currentUserIdRef` pattern was preserved and enhanced with better logging
3. **Added useCallback**: Wrapped `fetchProfile` in `useCallback` to satisfy React's exhaustive dependency rule and ensure stable function reference
4. **Added observability**: Added debug and error logging for profile fetch success/failure and stale response detection

### Code Changes
- Removed duplicate `fetchProfile` function (lines 75-89 in original)
- Wrapped `fetchProfile` in `useCallback` with empty dependency array
- Wrapped `signOut` in `useCallback` for consistency
- Added debug logging for successful profile loads
- Added error logging for failed profile fetches
- Added debug logging when stale responses are ignored

## Why This Fix Over Alternatives
**Alternative 1: Use a promise cancellation library**  
Rejected: Adds unnecessary complexity; the currentUserIdRef approach is simpler and effective.

**Alternative 2: Use AbortController for fetch cancellation**  
Rejected: Supabase client doesn't natively support AbortController; would require wrapping the client.

**Chosen approach**: The existing `currentUserIdRef` pattern was already correct but was being bypassed due to the duplicate function. This fix preserves the simple, effective pattern while cleaning up the code structure.

## Files Changed
- `frontend/src/store/authStore.jsx`

## Verification
```bash
# Run linter to verify no issues
npx @biomejs/biome lint frontend/src/store/authStore.jsx

# Expected: No errors
```

## Observability
The fix adds the following logging:
- `[Auth] Profile loaded successfully` - When profile fetch succeeds
- `[Auth] Profile fetch failed` - When profile fetch fails (with error details)
- `[Auth] Ignoring stale profile response` - When a stale response is detected and ignored (includes requestUserId and currentUserId)