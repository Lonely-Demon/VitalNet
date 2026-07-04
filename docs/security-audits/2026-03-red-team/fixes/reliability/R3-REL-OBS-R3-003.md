# Fix Log: R3-REL-OBS-R3-003

## Unit Details
- **Unit ID**: R3-REL-OBS-R3-003
- **Priority**: P2 MEDIUM
- **Title**: Safety-critical toasts auto-dismiss too quickly
- **Source IDs**: REL-OBS-R3-003
- **Location**: `frontend/src/components/ToastProvider.jsx:21`
- **Combined Fix**: false

## Issue Description
The ToastProvider auto-dismissed all toasts after 3000ms (3 seconds), including error and warning toasts that contain critical information about sync failures, connectivity issues, and submission errors. This was a reliability issue because:
1. Error/warning toasts would disappear before users could read them
2. Critical alerts about failed submissions were lost
3. Users had no way to see what went wrong after the toast disappeared

## Root Cause
The `showToast` function used a fixed 3000ms timeout for all toast types, with no distinction between informational toasts and safety-critical alerts.

## Fix Implementation

### Changes Made to `frontend/src/components/ToastProvider.jsx`:

1. **Dynamic duration based on toast type**:
   - Error and warning toasts: No auto-dismiss (stay until acknowledged)
   - Info and success toasts: 5 seconds (slightly longer for readability)
   - Custom duration: Optional parameter for specific use cases

2. **Added dismiss button for error/warning toasts**:
   - Error and warning toasts now include a close (×) button
   - Users can manually dismiss critical toasts when ready

3. **Updated API**:
   - Added `dismissToast` function to the context
   - Extended `showToast` signature to accept optional `duration` parameter

### Code Changes:
```jsx
const showToast = useCallback((message, type = 'info', duration = null) => {
    // ...
    const toastDuration = duration ?? (type === 'error' || type === 'warning' ? null : 5000)
    // ...
}, [])

const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
}, [])
```

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. Simply increase timeout for all toasts - Would make the UI feel sluggish
2. Add a "toast queue" with manual dismissal - Too complex for this issue
3. Only extend timeout for errors - Doesn't solve the acknowledgment problem

**Chosen approach:**
- Error/warning toasts stay until manually dismissed (no auto-dismiss)
- Info/success toasts have slightly longer duration (5s vs 3s)
- Added dismiss button for error/warning toasts

This approach balances usability (toasts don't block UI forever) with reliability (critical alerts are not lost).

## Files Changed
- `frontend/src/components/ToastProvider.jsx` - Modified showToast and added dismissToast

## Verification
- Build passes: `cd frontend && npm run build`
- No lint errors: `cd frontend && npx eslint src/components/ToastProvider.jsx`
- Manual verification: Error toasts stay visible until dismissed, success toasts auto-dismiss after 5s