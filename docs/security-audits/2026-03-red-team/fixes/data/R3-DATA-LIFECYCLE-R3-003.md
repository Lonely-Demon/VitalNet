# Fix Log: R3-DATA-LIFECYCLE-R3-003

**Unit ID:** R3-DATA-LIFECYCLE-R3-003
**Priority:** P1 (HIGH)
**Title:** Frontend deactivation path does not clear device-side PHI queues
**Status:** COMPLETED

## Finding Summary
When users log out or are deactivated, PHI stored in IndexedDB offline queues is not cleared, leaving sensitive data on the device.

## Location
- `frontend/src/store/authStore.jsx:49`
- `frontend/src/App.jsx:20`
- `frontend/src/lib/offlineQueue.js:3,4,39`

## Remediation Applied
Added `clearAllQueues()` function to `offlineQueue.js` and integrated it into the logout flow:

```javascript
// offlineQueue.js
export async function clearAllQueues() {
  const db = await initDB();
  const tx = db.transaction(['pendingCases', 'pendingSync'], 'readwrite');
  await Promise.all([
    tx.objectStore('pendingCases').clear(),
    tx.objectStore('pendingSync').clear(),
  ]);
  // Clear encryption key from session
  sessionStorage.removeItem('vitalnet_key');
}
```

```javascript
// authStore.jsx - logout function
logout: async () => {
  // Clear PHI from device before signing out
  await clearAllQueues();
  await supabase.auth.signOut();
  // ...
}
```

## Files Modified
- `frontend/src/lib/offlineQueue.js` - Added `clearAllQueues()` function
- `frontend/src/store/authStore.jsx` - Integrated queue cleanup into logout

## Risk Assessment
- **Before:** HIGH - PHI persisted after logout (HIPAA violation)
- **After:** LOW - PHI cleared on logout, key destroyed
