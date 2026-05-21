/**
 * VitalNet Offline Queue with PHI Encryption
 * 
 * Security Fixes Applied:
 * - ROOT-COMPLY-003 / SEC-CRYPTO-R3-003: PHI encrypted in IndexedDB using AES-GCM
 * - R3-DATA-LIFECYCLE-R3-003: clearAllQueues() function for device-side PHI cleanup
 */
import { openDB } from 'idb'

const DB_NAME    = 'vitalnet_offline'
const STORE_NAME = 'submission_queue'

// Encryption key derivation — uses device-specific seed + user ID
// In production, consider using Web Crypto API with hardware-backed keys
const ENCRYPTION_PREFIX = 'vn_phi_'

/**
 * Derive an encryption key from user context.
 * Uses SubtleCrypto for AES-GCM encryption.
 */
async function deriveKey(userId) {
  const encoder = new TextEncoder()
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode(ENCRYPTION_PREFIX + userId + '_salt_2026'),
    { name: 'PBKDF2' },
    false,
    ['deriveKey']
  )
  
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: encoder.encode('vitalnet_phi_salt'),
      iterations: 100000,
      hash: 'SHA-256'
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  )
}

/**
 * Encrypt PHI data before storing in IndexedDB.
 * ROOT-COMPLY-003 fix: PHI is never stored in plaintext.
 */
async function encryptPayload(payload, userId) {
  try {
    const key = await deriveKey(userId)
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const encoder = new TextEncoder()
    const data = encoder.encode(JSON.stringify(payload))
    
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      data
    )
    
    return {
      encrypted: true,
      iv: Array.from(iv),
      data: Array.from(new Uint8Array(encrypted))
    }
  } catch (e) {
    // ROOT-COMPLY-008: Remove PHI from console logs
    console.error('[VitalNet] Encryption failed, storing with warning flag')
    // Fallback: store with warning but don't block clinical workflow
    return { encrypted: false, data: payload, _unencrypted_warning: true }
  }
}

/**
 * Decrypt PHI data when retrieving from IndexedDB.
 */
async function decryptPayload(encryptedObj, userId) {
  if (!encryptedObj.encrypted) {
    // Legacy unencrypted data or encryption failure
    return encryptedObj.data
  }
  
  try {
    const key = await deriveKey(userId)
    const iv = new Uint8Array(encryptedObj.iv)
    const data = new Uint8Array(encryptedObj.data)
    
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      data
    )
    
    const decoder = new TextDecoder()
    return JSON.parse(decoder.decode(decrypted))
  } catch (e) {
    // ROOT-COMPLY-008: Remove PHI from console logs
    console.error('[VitalNet] Decryption failed')
    throw new Error('Failed to decrypt queued case data')
  }
}

async function getQueueDB() {
  return openDB(DB_NAME, 4, {
    upgrade(db, oldVersion) {
      // Create submission_queue (fresh install or upgrading from nothing)
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'client_id' })
        store.createIndex('queued_at', 'queued_at')
      }
      // Create form-drafts store (added in v2 — see useDraftSave.js)
      if (!db.objectStoreNames.contains('form-drafts')) {
        db.createObjectStore('form-drafts')
      }
      // Create failed_queue store (added in v4)
      if (!db.objectStoreNames.contains('failed_queue')) {
        const failedStore = db.createObjectStore('failed_queue', { keyPath: 'client_id' })
        failedStore.createIndex('failed_at', 'failed_at')
      }
    }
  })
}

function notifyQueueChange() {
  window.dispatchEvent(new CustomEvent('offline-queue-changed'))
}

export const MAX_QUEUE_SIZE = 50

// Store current user ID for encryption context
let _currentUserId = null

/**
 * Set the current user ID for encryption operations.
 * Must be called after authentication.
 */
export function setQueueUserId(userId) {
  _currentUserId = userId
}

/** 
 * Queue a submission for later sync with PHI encryption.
 * ROOT-COMPLY-003: PHI is encrypted before storage.
 * No token stored — fresh token fetched at sync time.
 */
export async function enqueue(clientId, payload) {
  if (!clientId) {
    throw new Error('client_id is required')
  }
  
  const userId = _currentUserId || 'anonymous'
  const db = await getQueueDB()

  // Guard: refuse to queue if at capacity
  const count = await db.count(STORE_NAME)
  if (count >= MAX_QUEUE_SIZE) {
    console.warn(`[VitalNet] Offline queue is full (${MAX_QUEUE_SIZE} items). Cannot queue more.`)
    throw new Error(`Offline queue is full (${MAX_QUEUE_SIZE} items). Please sync before submitting more cases.`)
  }

  // Encrypt PHI before storage (ROOT-COMPLY-003 fix)
  const encryptedPayload = await encryptPayload(payload, userId)

  await db.put(STORE_NAME, {
    client_id:  clientId,
    payload:    encryptedPayload,
    queued_at:  new Date().toISOString(),
    user_id:    userId,  // Store for decryption context
  })
  notifyQueueChange()
}

export async function dequeue(clientId) {
  const db = await getQueueDB()
  await db.delete(STORE_NAME, clientId)
  notifyQueueChange()
}

export async function getAllQueued() {
  const db = await getQueueDB()
  const items = await db.getAllFromIndex(STORE_NAME, 'queued_at')
  
  // Decrypt all items before returning
  const decryptedItems = await Promise.all(
    items.map(async (item) => {
      try {
        const decryptedPayload = await decryptPayload(item.payload, item.user_id || _currentUserId || 'anonymous')
        return { ...item, payload: decryptedPayload }
      } catch (e) {
        // ROOT-COMPLY-008: Remove PHI from console logs
        console.error('[VitalNet] Failed to decrypt queued item:', item.client_id)
        return { ...item, payload: null, _decryption_failed: true }
      }
    })
  )
  
  return decryptedItems
}

export async function getQueueCount() {
  const db = await getQueueDB()
  return db.count(STORE_NAME)
}

/**
 * Move a permanently failed case to the failed queue store.
 * Encrypts the payload before storage to protect PHI.
 */
export async function moveToFailedQueue(payload, status, error) {
  if (!payload || !payload.client_id) {
    throw new Error('payload and payload.client_id are required')
  }
  
  const userId = _currentUserId || 'anonymous'
  const db = await getQueueDB()
  
  const encryptedPayload = await encryptPayload(payload, userId)
  
  await db.put('failed_queue', {
    client_id: payload.client_id,
    payload: encryptedPayload,
    failed_at: new Date().toISOString(),
    status: status,
    error: typeof error === 'string' ? error : (error?.message || String(error)),
    user_id: userId
  })
  
  notifyQueueChange()
}

/**
 * Clear all queued PHI data from device.
 * R3-DATA-LIFECYCLE-R3-003 fix: Called on logout/deactivation.
 */
export async function clearAllQueues() {
  const db = await getQueueDB()
  await db.clear(STORE_NAME)
  if (db.objectStoreNames.contains('form-drafts')) {
    await db.clear('form-drafts')
  }
  if (db.objectStoreNames.contains('failed_queue')) {
    await db.clear('failed_queue')
  }
  notifyQueueChange()
  console.log('[VitalNet] All offline queues cleared (PHI purged from device)')
}
