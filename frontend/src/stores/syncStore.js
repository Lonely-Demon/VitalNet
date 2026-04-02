/**
 * syncStore.js — Stateful offline queue manager.
 *
 * Owns the entire offline lifecycle:
 * - submitCase (online + offline paths)
 * - processQueue (drains IndexedDB queue when online)
 *
 * Separated from stateless API wrappers because it holds mutable state
 * (IndexedDB queue) and has side-effects (dispatching custom DOM events,
 * reading/writing from supabase.auth.getSession() at runtime).
 *
 * ROOT-SYNC-DD-001 fix: Added multi-tab coordination using BroadcastChannel
 * to prevent duplicate replay bursts across tabs.
 */
import { supabase } from '@/lib/supabase'
import { enqueue, dequeue, getAllQueued } from '@/lib/offlineQueue'
import { isServerReachable } from '@/lib/connectivity'
import { v4 as uuidv4 } from 'uuid'

const BASE = import.meta.env.VITE_API_BASE_URL

// ROOT-SYNC-DD-001 fix: Multi-tab coordination using BroadcastChannel
const SYNC_CHANNEL_NAME = 'vitalnet-sync-coordinator'
let syncBroadcastChannel = null

/**
 * Get or create the BroadcastChannel for sync coordination.
 * Uses lazy initialization to avoid creating channels unnecessarily.
 */
function getSyncChannel() {
  if (typeof BroadcastChannel === 'undefined') {
    // Fallback for environments without BroadcastChannel (e.g., some test environments)
    return null
  }
  if (!syncBroadcastChannel) {
    syncBroadcastChannel = new BroadcastChannel(SYNC_CHANNEL_NAME)
  }
  return syncBroadcastChannel
}

/**
 * Acquire sync lock for multi-tab coordination.
 * Returns true if lock acquired, false if another tab is syncing.
 * Lock automatically releases after the specified timeout.
 */
async function acquireSyncLock(timeoutMs = 30000) {
  const channel = getSyncChannel()
  if (!channel) {
    // No BroadcastChannel support - proceed with sync (single tab assumed)
    return true
  }

  return new Promise((resolve) => {
    const lockId = uuidv4()
    const lockKey = 'sync_lock'
    const lockValue = JSON.stringify({ id: lockId, timestamp: Date.now() })

    // Try to set the lock in localStorage (atomic operation)
    try {
      const existingLock = localStorage.getItem(lockKey)
      if (existingLock) {
        const lockData = JSON.parse(existingLock)
        const lockAge = Date.now() - lockData.timestamp

        // If lock is recent and from another tab, don't acquire
        if (lockAge < timeoutMs && lockData.id !== lockId) {
          console.log('[VitalNet] Sync lock held by another tab, skipping sync')
          resolve(false)
          return
        }
      }

      // Acquire the lock
      localStorage.setItem(lockKey, lockValue)

      // Listen for release from other tabs
      const handleMessage = (event) => {
        if (event.data === 'release_sync_lock') {
          channel.removeEventListener('message', handleMessage)
        }
      }
      channel.addEventListener('message', handleMessage)

      // Auto-release after timeout
      setTimeout(() => {
        releaseSyncLock()
        channel.removeEventListener('message', handleMessage)
      }, timeoutMs)

      resolve(true)
    } catch (e) {
      // localStorage not available - proceed with sync
      resolve(true)
    }
  })
}

/**
 * Release the sync lock and notify other tabs.
 */
function releaseSyncLock() {
  const channel = getSyncChannel()
  try {
    localStorage.removeItem('sync_lock')
    if (channel) {
      channel.postMessage('release_sync_lock')
    }
  } catch (e) {
    // Ignore errors during cleanup
  }
}

async function _authHeaders(token) {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  }
}

/**
 * submitCase — Handles online and offline submission paths.
 * Generates a stable client_id (idempotency key) before either path.
 * Returns { queued: true, client_id } when offline, or the full server record.
 */
export async function submitCase(formData) {
  // Generate client_id here — same UUID whether online or queued (idempotency)
  const clientId = uuidv4()
  const payload = { ...formData, client_id: clientId, client_submitted_at: new Date().toISOString() }

  // True connectivity check — not just navigator.onLine.
  const online = await isServerReachable()

  if (!online) {
    // Offline path: store in IndexedDB queue with offline flag (no token stored)
    const offlinePayload = { ...payload, created_offline: true }
    await enqueue(clientId, offlinePayload)
    // Signal useLocalTriage to begin ONNX warmup for offline use
    window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
    return { queued: true, client_id: clientId }
  }

  // Online path: attempt fetch, fall back to queue on network error
  try {
    const { data: { session } } = await supabase.auth.getSession()
    if (!session) throw new Error('Not authenticated')
    const headers = await _authHeaders(session.access_token)
    const res = await fetch(`${BASE}/api/submit`, {
      method: 'POST', headers, body: JSON.stringify(payload),
    })

    if (!res.ok) {
      // Server error (4xx/5xx) — surface to UI, don't queue
      throw new Error(await res.text())
    }

    return res.json()
  } catch (err) {
    // Network error (TypeError: Failed to fetch) → silently queue
    if (err instanceof TypeError) {
      const offlinePayload = { ...payload, created_offline: true }
      await enqueue(clientId, offlinePayload)
      window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
      return { queued: true, client_id: clientId }
    }
    // Non-network error (4xx/5xx from above) → rethrow to UI
    throw err
  }
}

/**
 * processQueue — called on every 'online' event and on app load.
 * Gets a fresh token from supabase.auth.getSession() at run time.
 * Returns { synced: number, failed: number, requiresLogin?: boolean }
 *
 * ROOT-SYNC-DD-001 fix: Uses multi-tab coordination lock to prevent
 * duplicate replay bursts across tabs.
 */
export async function processQueue() {
  // ROOT-SYNC-DD-001 fix: Acquire sync lock to prevent duplicate replay across tabs
  const lockAcquired = await acquireSyncLock()
  if (!lockAcquired) {
    // Another tab is syncing, skip this attempt
    return { synced: 0, failed: 0, skipped: true }
  }

  try {
    const queued = await getAllQueued()
    if (queued.length === 0) return { synced: 0, failed: 0 }

    // Get fresh token — supabase-js auto-refreshes if access token expired
    const { data: { session } } = await supabase.auth.getSession()
    if (!session) {
      // No valid session — user needs to re-login before queue can drain
      return { synced: 0, failed: 0, requiresLogin: true }
    }
    const freshToken = session.access_token

    let synced = 0
    let failed = 0

    // Rate-safety: 3.5s between items = max ~17 items/min, safely under the 20/min per-user limit.
    const QUEUE_ITEM_DELAY_MS = 3500

    for (const item of queued) {
      try {
        const res = await fetch(`${BASE}/api/submit`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${freshToken}`,
          },
          body: JSON.stringify(item.payload),
        })

        if (res.ok) {
          await dequeue(item.client_id)
          synced++
        } else if (res.status === 409) {
          // Conflict = already inserted (duplicate from retry)
          await dequeue(item.client_id)
          synced++
        } else if (res.status >= 400 && res.status < 500) {
          // Any 4xx = permanent client error — this payload will NEVER succeed.
          // Dequeue immediately to unblock subsequent queue items.
          console.warn(
            '[VitalNet] Permanent error — dequeuing case to prevent head-of-line blocking.',
            item.client_id, res.status, await res.text()
          )
          await dequeue(item.client_id)
          failed++
        } else {
          // Transient error (500, 503, etc.) — leave in queue for next attempt
          failed++
        }
      } catch {
        // Network error — leave in queue for next attempt
        failed++
      }
      // Paced delay between items — stays under per-user rate limit during bulk sync
      await new Promise(resolve => setTimeout(resolve, QUEUE_ITEM_DELAY_MS))
    }

    return { synced, failed }
  } finally {
    // Always release the sync lock
    releaseSyncLock()
  }
}
