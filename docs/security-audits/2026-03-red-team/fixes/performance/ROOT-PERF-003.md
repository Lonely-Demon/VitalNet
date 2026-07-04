# Fix Log: ROOT-PERF-003 - Realtime Subscription Memory Leak on Unmount

## Issue Description
The `useRealtimeCases` hook had a potential memory leak where the cleanup function in `useEffect` was not properly cleaning up realtime subscriptions when the component unmounted. The cleanup function was referencing the `channel` variable from the current render scope rather than using the channel stored in the ref, which could lead to scenarios where the wrong channel is cleaned up or no channel at all.

## Applied Fix
Updated the cleanup function in `useRealtimeCases.js` to properly use the channel reference stored in the ref, ensuring that the correct channel is always unsubscribed when the component unmounts.

Specifically, the fix changes the cleanup function from:
```javascript
return () => {
  supabase.removeChannel(channel)
}
```

to:
```javascript
return () => {
  supabase.removeChannel(channelRef.current)
}
```

## Why This Fix
This fix was chosen because:
1. It ensures the correct channel is always used for cleanup
2. It follows the standard React pattern of using refs for mutable values that don't trigger re-renders
3. It's a minimal, safe change that doesn't affect functionality but ensures proper cleanup
4. It prevents potential memory leaks by ensuring all realtime subscriptions are properly removed

## Files Changed
- `frontend/src/hooks/useRealtimeCases.js`

## Verification
The fix was verified by reviewing the code pattern which now correctly uses refs to maintain channel references for proper cleanup. The Supabase `removeChannel` method will now always be called with the correct channel reference from the ref, ensuring proper cleanup of realtime subscriptions.