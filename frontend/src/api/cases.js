/**
 * cases.js — Stateless API wrappers for patient case endpoints.
 */
import { authHeaders } from '@/api/auth'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function getCases({ before_time, before_priority } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases`)
  if (before_time) url.searchParams.set('before_time', before_time)
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

export async function getMySubmissions({ before } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases/mine`)
  if (before) url.searchParams.set('before', before)
  url.searchParams.set('limit', '25')
  const res = await fetch(url.toString(), { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { cases, hasMore, nextCursor }
}
