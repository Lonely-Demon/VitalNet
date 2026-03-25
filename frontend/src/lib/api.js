import { supabase } from './supabase'
import { enqueue, dequeue, getAllQueued } from './offlineQueue'
import { v4 as uuidv4 } from 'uuid'
import { isServerReachable } from './connectivity'

const BASE = import.meta.env.VITE_API_BASE_URL

async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return {
    'Content-Type':  'application/json',
    'Authorization': `Bearer ${session.access_token}`,
  }
}

export async function submitCase(formData) {
  // Generate client_id here — same UUID whether online or queued (idempotency)
  const clientId = uuidv4()
  const payload  = { ...formData, client_id: clientId, client_submitted_at: new Date().toISOString() }

  // True connectivity check — not just navigator.onLine.
  // navigator.onLine is true even when the satellite link is down but local Wi-Fi is up.
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
    const headers = await authHeaders()
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
      // Server appeared online but connection failed — trigger ONNX warmup
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
 */
export async function processQueue() {
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
  // Without this delay, a bulk sync of 20 queued cases would exhaust the limit on the last item.
  const QUEUE_ITEM_DELAY_MS = 3500

  for (const item of queued) {
    try {
      const res = await fetch(`${BASE}/api/submit`, {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json',
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
        // Covers 422 (schema mismatch), 400 (bad request), 403 (auth expired), etc.
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
}

// ─── Unchanged functions below ───────────────────────────────────────────────

export async function getCases({ before_time, before_priority } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases`)
  if (before_time)     url.searchParams.set('before_time', before_time)
  if (before_priority !== undefined && before_priority !== null) {
    url.searchParams.set('before_priority', String(before_priority))
  }
  url.searchParams.set('limit', '25')
  const res = await fetch(url.toString(), { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { cases, hasMore, nextCursor, nextTriagePriority }
}

export async function reviewCase(caseId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/${caseId}/review`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Users ──────────────────────────────────────────────────────────────

export async function adminListUsers() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateUser(data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminUpdateUser(userId, data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}`, {
    method: 'PATCH', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminDeactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminReactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}/reactivate`, {
    method: 'POST', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Facilities ─────────────────────────────────────────────────────────

export async function adminListFacilities() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateFacility(data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminToggleFacility(facilityId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities/${facilityId}/toggle`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Stats ──────────────────────────────────────────────────────────────

export async function adminGetStats() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/stats`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── ASHA: Submission history ──────────────────────────────────────────────────

export async function getMySubmissions({ before } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases/mine`)
  if (before) url.searchParams.set('before', before)
  url.searchParams.set('limit', '25')
  const res = await fetch(url.toString(), { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { cases, hasMore, nextCursor }
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export async function getAnalyticsSummary() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/analytics/summary`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getEmergencyRate() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/analytics/emergency-rate`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
