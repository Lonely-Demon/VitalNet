# Fix Log: ROOT-COMPLY-004

**Unit ID:** ROOT-COMPLY-004
**Priority:** P1 (HIGH)
**Title:** No session inactivity timeout
**Status:** COMPLETED

## Finding Summary
User sessions remained active indefinitely, even when users stepped away from devices, potentially exposing PHI to unauthorized physical access.

## Location
`frontend/src/store/authStore.jsx`

## Remediation Applied
Added 15-minute inactivity timeout in `authStore.jsx`:

```javascript
// Session timeout configuration (15 minutes)
const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000;

// Activity tracking
let inactivityTimer = null;

function resetInactivityTimer() {
  if (inactivityTimer) clearTimeout(inactivityTimer);
  inactivityTimer = setTimeout(() => {
    useAuth.getState().logout();
    // Show timeout notification
  }, INACTIVITY_TIMEOUT_MS);
}

// Listen for user activity
['mousedown', 'keydown', 'touchstart', 'scroll'].forEach(event => {
  window.addEventListener(event, resetInactivityTimer, { passive: true });
});
```

## Configuration
- **Timeout duration:** 15 minutes (configurable via constant)
- **Activity triggers:** Mouse, keyboard, touch, scroll events
- **On timeout:** Automatic logout with PHI cleanup

## Files Modified
- `frontend/src/store/authStore.jsx` - Added inactivity timeout logic

## Risk Assessment
- **Before:** HIGH - Unattended sessions exposed PHI
- **After:** LOW - Automatic logout after 15 minutes of inactivity
