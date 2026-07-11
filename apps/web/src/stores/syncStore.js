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

  // True connectivity check — not just navigator.onLine.
  const online = await isServerReachable()

  if (!online) {
    // Offline path: queue in the outbox with offline flag (no token stored)
    const offlinePayload = { ...payload, created_offline: true }
    await enqueue(clientId, 'case.submit', offlinePayload)
    // Signal useLocalTriage to begin offline-model warmup
    window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
    return { queued: true, client_id: clientId }
  }

  // Online path: attempt fetch, fall back to queueing on network error
  try {
    const { data: { session } } = await supabase.auth.getSession()
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
      await enqueue(clientId, 'case.submit', offlinePayload)
      window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
      return { queued: true, client_id: clientId }
    }
    // Non-network error (4xx/5xx from above) → rethrow to UI
    throw err
  }
}

// Rate-safety: 3.5s between items = max ~17 items/min, safely under the 20/min per-user limit.
const QUEUE_ITEM_DELAY_MS = 3500

/** Drains a single 'case.submit' outbox event. Returns 'synced' | 'failed' | 'dead'. */
async function drainCaseSubmit(item, token) {
  const res = await fetch(`${apiBase('cases.submit')}/api/submit`, {
    method: 'POST',
    headers: { ...buildAuthHeaders(token), 'X-Event-Id': item.event_id },
    body: JSON.stringify(item.payload),
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
    // Dead-letter rather than dequeue-and-forget, so the worker can see
    // (and, once reviewed, discard or retry) what failed instead of it
    // silently vanishing — see lib/outbox.js's getDeadLetters().
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

/**
 * processQueue — called on every 'online' event and on app load.
 * Gets a fresh token from supabase.auth.getSession() at run time.
 * Returns { synced: number, failed: number, dead: number, requiresLogin?: boolean }
 */
export async function processQueue() {
  const pending = await getPendingEvents()
  if (pending.length === 0) return { synced: 0, failed: 0, dead: 0 }

  // Get fresh token — supabase-js auto-refreshes if access token expired
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) {
    // No valid session — user needs to re-login before the outbox can drain
    return { synced: 0, failed: 0, dead: 0, requiresLogin: true }
  }
  const freshToken = session.access_token

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
        default:
          // Unknown event type (should never happen — enqueue() only ever
          // writes types this drain loop knows about) — dead-letter rather
          // than loop on it forever.
          console.warn(`[VitalNet] Unknown outbox event type "${item.type}" — dead-lettering.`, item.event_id)
          await markDead(item.event_id, `Unknown event type: ${item.type}`)
          outcome = 'dead'
      }
      if (outcome === 'synced') synced++
      else if (outcome === 'dead') dead++
      else failed++
    } catch {
      // Network error — leave in queue for next attempt
      await incrementAttempts(item.event_id)
      failed++
    }
    // Paced delay between items — stays under per-user rate limit during bulk sync
    await new Promise(resolve => setTimeout(resolve, QUEUE_ITEM_DELAY_MS))
  }

  return { synced, failed, dead }
}
