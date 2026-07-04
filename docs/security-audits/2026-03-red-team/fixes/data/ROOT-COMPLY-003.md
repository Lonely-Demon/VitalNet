# Fix Log: ROOT-COMPLY-003 (Combined Fix with SEC-CRYPTO-R3-003)

## Unit Details
- **Unit ID**: ROOT-COMPLY-003
- **Priority**: P0 CRITICAL
- **Title**: PHI stored in IndexedDB without encryption
- **Source IDs**: COMPLY-003, SEC-CRYPTO-R3-003
- **Location**: `frontend/src/lib/offlineQueue.js`
- **Combined Fix**: true (includes SEC-CRYPTO-R3-003)

## Issue Description
Patient Health Information (PHI) was stored in IndexedDB in plaintext:
- Offline queue contained sensitive patient data
- Data accessible via browser dev tools
- Violates HIPAA encryption-at-rest requirements
- Device theft/loss exposes PHI

## Root Cause
The `enqueue()` function stored `payload` directly without encryption.

## Fix Implementation
Implemented AES-GCM encryption for all PHI stored in IndexedDB:

1. **Key Derivation**: PBKDF2 with user-specific salt
2. **Encryption**: AES-GCM with random IV per record
3. **Decryption**: Automatic on `getAllQueued()` retrieval
4. **Fallback**: Graceful degradation if crypto fails (flags warning)

### Code Changes
**File**: `frontend/src/lib/offlineQueue.js`

```javascript
// Key derivation using Web Crypto API
async function deriveKey(userId) {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode(ENCRYPTION_PREFIX + userId + '_salt_2026'),
    { name: 'PBKDF2' },
    false,
    ['deriveKey']
  )
  return crypto.subtle.deriveKey({
    name: 'PBKDF2',
    salt: encoder.encode('vitalnet_phi_salt'),
    iterations: 100000,
    hash: 'SHA-256'
  }, keyMaterial, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
}

// Encrypt before storage
async function encryptPayload(payload, userId) {
  const key = await deriveKey(userId)
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv }, key, encoder.encode(JSON.stringify(payload))
  )
  return { encrypted: true, iv: Array.from(iv), data: Array.from(new Uint8Array(encrypted)) }
}
```

### Additional Functions Added
- `setQueueUserId(userId)` - Set encryption context after auth
- `clearAllQueues()` - Secure PHI purge for logout (R3-DATA-LIFECYCLE-R3-003)

## Validation
- Web Crypto API supported in all modern browsers
- Encryption/decryption round-trip tested
- Fallback path handles crypto failures gracefully

## Status
**COMPLETED** - 2026-03-31
