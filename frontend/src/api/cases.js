/**
 * cases.js — Stateless API wrappers for patient case endpoints.
 *
 * Reliability improvements (ROOT-CHAOS-003):
 * - Centralized timeout wrapper (10s reads, 30s writes)
 * - Retry logic with exponential backoff
 */
import { authHeaders } from '@/api/auth'
import { fetchWithRetry } from './retry'

const BASE = import.meta.env.VITE_API_BASE_URL

// Timeouts for case operations (ms)
const CASE_READ_TIMEOUT_MS = 10000
const CASE_WRITE_TIMEOUT_MS = 30000

/**
 * ROOT-PERF-004 + R3-PERF-VITALS-R3-005
 * Supports both explicit cursor fields and a `before` cursor object/string.
 */
export async function getCases({ before, before_time, before_priority, before_id } = {}) {
  let resolvedBeforeTime = before_time
  let resolvedBeforePriority = before_priority
  let resolvedBeforeId = before_id

  if (before && typeof before === 'object') {
    resolvedBeforeTime = before.time ?? before_time
    resolvedBeforePriority = before.priority ?? before_priority
    resolvedBeforeId = before.id ?? before_id
  } else if (typeof before === 'string' && !before_time) {
    // Backward compatibility for old callers passing just timestamp string
    resolvedBeforeTime = before
  }

  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases`)

  if (resolvedBeforeTime) url.searchParams.set('before_time', resolvedBeforeTime)
  if (resolvedBeforePriority !== undefined && resolvedBeforePriority !== null) {
    url.searchParams.set('before_priority', String(resolvedBeforePriority))
  }
  if (resolvedBeforeId) {
    url.searchParams.set('before_id', resolvedBeforeId)
  }
  url.searchParams.set('limit', '25')

  const res = await fetchWithRetry(
    url.toString(),
    { headers },
    { timeoutMs: CASE_READ_TIMEOUT_MS, maxRetries: 2 }
  )
  if (!res.ok) throw new Error(await res.text())
  return res.json() // Returns { cases, hasMore, nextCursor, nextTriagePriority, nextId }
}

export async function reviewCase(caseId) {
  const headers = await authHeaders()
  const res = await fetchWithRetry(
    `${BASE}/api/cases/${caseId}/review`,
    { method: 'PATCH', headers },
    { timeoutMs: CASE_WRITE_TIMEOUT_MS, maxRetries: 2 }
  )
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getMySubmissions({ before, before_id } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases/mine`)
  if (before) url.searchParams.set('before', before)
  if (before_id) url.searchParams.set('before_id', before_id)
  url.searchParams.set('limit', '25')

  const res = await fetchWithRetry(
    url.toString(),
    { headers },
    { timeoutMs: CASE_READ_TIMEOUT_MS, maxRetries: 2 }
  )
  if (!res.ok) throw new Error(await res.text())
  return res.json() // Returns { cases, hasMore, nextCursor, nextId }
}
