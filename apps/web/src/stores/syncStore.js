/**
 * syncStore.js — Stateful offline outbox manager (Round 6 rebuild plan,
 * Phase 5: "syncStore.js becomes a thin outbox client").
 *
 * Owns the entire offline lifecycle:
 *   - submitCase (online + offline paths) — enqueues a type:'case.submit'
 *     outbox event on failure, rather than a case-submission-specific queue.
 *   - processQueue (drains the outbox when online) — dispatches by
 *     event.type; only 'case.submit' exists today (doctor actions stay
 *     online-only), but the drain loop is written to route on type so a
 *     future offline-capable action doesn't need a second drain loop.
 *
 * Separated from stateless API wrappers because it holds mutable state
 * (the IndexedDB outbox) and has side-effects (dispatching custom DOM
 * events, reading/writing from supabase.auth.getSession() at runtime).
 *
 * Every request that touches the outbox sends X-Event-Id: <event_id> — the
 * SAME uuid used as the outbox row's key and case_records.client_id.
 * apps/api's idempotency middleware (_shared/idempotency.ts) replays the
 * stored response for a repeated event_id instead of re-running the
 * handler, so a retried drain (flaky connectivity, an app restart mid-sync)
 * never re-runs triage/the LLM briefing call for a case already recorded.
 */
import { supabase } from '@/lib/supabase'
import { enqueue, dequeue, getPendingEvents, markDead, incrementAttempts } from '@/lib/outbox'
import { isServerReachable } from '@/lib/connectivity'
import { buildAuthHeaders } from '@/api/auth'
import { apiBase } from '@/api/base'
import { v4 as uuidv4 } from 'uuid'

/**
 * submitCase — Handles online and offline submission paths.
 * Generates a stable client_id (idempotency key, also the outbox event_id)
 * before either path. Returns { queued: true, client_id } when offline, or
 * the full server record.
 */
export async function submitCase(formData) {
  // Generate client_id here — same UUID whether online or queued (idempotency)
  const clientId = uuidv4()
  const payload = { ...formData, client_id: clientId, client_submitted_at: new Date().toISOString() }

  // The queuing worker's identity — stamped onto any outbox row so that only
  // this same worker can later drain it (never whoever is logged in at sync
  // time on a shared PHC tablet). getSession() reads local storage, so this
  // resolves offline too.
  const { data: { session } } = await supabase.auth.getSession()
  const ownerId = session?.user?.id ?? null

  // True connectivity check — not just navigator.onLine.
  const online = await isServerReachable()

  if (!online) {
    // Offline path: queue in the outbox with offline flag (no token stored)
    const offlinePayload = { ...payload, created_offline: true }
    await enqueue(clientId, 'case.submit', offlinePayload, ownerId)
    // Signal useLocalTriage to begin offline-model warmup
    window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
    return { queued: true, client_id: clientId }
  }

  // Online path: attempt fetch, fall back to queueing on network error
  try {
    if (!session) throw new Error('Not authenticated')
    const headers = { ...buildAuthHeaders(session.access_token), 'X-Event-Id': clientId }
    const res = await fetch(`${apiBase('cases.submit')}/api/submit`, {
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
      await enqueue(clientId, 'case.submit', offlinePayload, ownerId)
      window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
      return { queued: true, client_id: clientId }
    }
    // Non-network error (4xx/5xx from above) → rethrow to UI
    throw err
  }
}

// Rate-safety: 3.5s between items = max ~17 items/min, safely under the 20/min per-user limit.
const QUEUE_ITEM_DELAY_MS = 3500

let _activeDrainPromise = null

/** Drains a single 'case.submit' outbox event. Reconciles clock skew using boot-relative monotonic offset. */
async function drainCaseSubmit(item, token) {
  const payload = { ...item.payload }
  // BUG-06: Cross-tab / reload resilient monotonic calculation
  if (
    typeof performance !== 'undefined' &&
    typeof performance.now === 'function' &&
    item.intake_monotonic_ms != null
  ) {
    let elapsedMs = null
    const currentOrigin = typeof performance.timeOrigin === 'number' ? performance.timeOrigin : null
    const itemOrigin = typeof item.enqueued_time_origin === 'number' ? item.enqueued_time_origin : null

    if (itemOrigin != null && currentOrigin != null) {
      const enqueuedAbsolute = itemOrigin + item.intake_monotonic_ms
      const currentAbsolute = currentOrigin + performance.now()
      if (currentAbsolute >= enqueuedAbsolute) {
        elapsedMs = Math.round(currentAbsolute - enqueuedAbsolute)
      }
    } else if (itemOrigin == null && performance.now() >= item.intake_monotonic_ms) {
      elapsedMs = Math.round(performance.now() - item.intake_monotonic_ms)
    }

    if (elapsedMs != null && elapsedMs >= 0) {
      payload.client_submitted_at = new Date(Date.now() - elapsedMs).toISOString()
    } else if (!payload.client_submitted_at && item.created_at) {
      payload.client_submitted_at = item.created_at
    }
  } else if (!payload.client_submitted_at && item.created_at) {
    payload.client_submitted_at = item.created_at
  }

  const res = await fetch(`${apiBase('cases.submit')}/api/submit`, {
    method: 'POST',
    headers: { ...buildAuthHeaders(token), 'X-Event-Id': item.event_id },
    body: JSON.stringify(payload),
  })

  if (res.ok) {
    await dequeue(item.event_id)
    return 'synced'
  }
  if (res.status === 409) {
    // Conflict = already inserted (duplicate from retry)
    await dequeue(item.event_id)
    return 'synced'
  }
  if (res.status >= 400 && res.status < 500) {
    // Any 4xx = permanent client error — this payload will NEVER succeed as-is.
    const detail = await res.text()
    console.warn(
      '[VitalNet] Permanent error — dead-lettering to prevent head-of-line blocking.',
      item.event_id, res.status, detail,
    )
    await markDead(item.event_id, `HTTP ${res.status}: ${detail}`.slice(0, 500))
    return 'dead'
  }
  // Transient error (500, 503, etc.) — leave in queue for next attempt
  await incrementAttempts(item.event_id)
  return 'failed'
}

/** Drains a 'case.revoke_consent' outbox tombstone event (ADR §55). */
async function drainConsentRevoke(item, token) {
  const clientId = item.payload?.client_id || item.event_id
  const res = await fetch(`${apiBase('cases.submit')}/api/security/cases/${clientId}/revoke-consent`, {
    method: 'POST',
    headers: { ...buildAuthHeaders(token), 'X-Event-Id': item.event_id },
    body: JSON.stringify(item.payload || {}),
  })

  if (res.ok || res.status === 409) {
    await dequeue(item.event_id)
    return 'synced'
  }
  // BUG-08: Do not drop revocation immediately on 404 (e.g. if case.submit hasn't synced yet)
  if (res.status === 404) {
    if ((item.attempts || 0) < 3) {
      await incrementAttempts(item.event_id)
      return 'failed'
    }
    const detail = await res.text()
    console.warn('[VitalNet] Consent revocation 404 after retries — dead-lettering', item.event_id, detail)
    await markDead(item.event_id, `HTTP 404: Case not found for revocation: ${detail}`.slice(0, 500))
    return 'dead'
  }
  if (res.status >= 400 && res.status < 500) {
    const detail = await res.text()
    console.warn('[VitalNet] Consent revocation error — dead-lettering', item.event_id, res.status, detail)
    await markDead(item.event_id, `HTTP ${res.status}: ${detail}`.slice(0, 500))
    return 'dead'
  }
  await incrementAttempts(item.event_id)
  return 'failed'
}

/**
 * processQueue — called on every 'online' event and on app load.
 * Gets a fresh token from supabase.auth.getSession() at run time.
 * Returns { synced: number, failed: number, dead: number, requiresLogin?: boolean }
 */
export async function processQueue() {
  if (_activeDrainPromise) {
    return _activeDrainPromise
  }

  _activeDrainPromise = (async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        return { synced: 0, failed: 0, dead: 0, requiresLogin: true }
      }
      const freshToken = session.access_token
      const ownerId = session.user.id

      const pending = await getPendingEvents(ownerId)
      if (pending.length === 0) return { synced: 0, failed: 0, dead: 0 }

      let synced = 0
      let failed = 0
      let dead = 0

      for (const item of pending) {
        try {
          let outcome
          switch (item.type) {
            case 'case.submit':
              outcome = await drainCaseSubmit(item, freshToken)
              break
            case 'case.revoke_consent':
              outcome = await drainConsentRevoke(item, freshToken)
              break
            default:
              console.warn(`[VitalNet] Unknown outbox event type "${item.type}" — dead-lettering.`, item.event_id)
              await markDead(item.event_id, `Unknown event type: ${item.type}`)
              outcome = 'dead'
          }
          if (outcome === 'synced') synced++
          else if (outcome === 'dead') dead++
          else failed++
        } catch {
          await incrementAttempts(item.event_id)
          failed++
        }
        await new Promise(resolve => setTimeout(resolve, QUEUE_ITEM_DELAY_MS))
      }

      return { synced, failed, dead }
    } finally {
      _activeDrainPromise = null
    }
  })()

  return _activeDrainPromise
}
