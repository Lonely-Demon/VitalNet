/**
 * cases.js — Stateless API wrappers for patient case endpoints.
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function getCases({ before_time, before_priority, before_id } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases`)
  if (before_time) url.searchParams.set('before_time', before_time)
  if (before_priority !== undefined && before_priority !== null) {
    url.searchParams.set('before_priority', String(before_priority))
  }
  if (before_id) url.searchParams.set('before_id', before_id)
  url.searchParams.set('limit', '25')
  const res = await getWithRetry(url.toString(), headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { cases, hasMore, nextCursor, nextTriagePriority, nextId }
}

export async function reviewCase(caseId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/${caseId}/review`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function overrideTriage(caseId, { overridden_triage, override_reason }) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/${caseId}/triage-override`, {
    method: 'PATCH', headers,
    body: JSON.stringify({ overridden_triage, override_reason }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function recordCaseOutcome(caseId, { actual_severity, patient_disposition, outcome_notes }) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/${caseId}/outcome`, {
    method: 'PATCH', headers,
    body: JSON.stringify({ actual_severity, patient_disposition, outcome_notes }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getPatientSummary(caseId, language) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases/${caseId}/patient-summary`)
  if (language) url.searchParams.set('language', language)
  const res = await fetch(url.toString(), { method: 'POST', headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { summary, generated }
}

export async function getCaseHistoryByPatientKey(patientKey) {
  const headers = await authHeaders()
  const res = await getWithRetry(`${BASE}/api/cases/by-patient-key/${encodeURIComponent(patientKey)}`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { cases }
}

export async function getMySubmissions({ before, before_id } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/cases/mine`)
  if (before) url.searchParams.set('before', before)
  if (before_id) url.searchParams.set('before_id', before_id)
  url.searchParams.set('limit', '25')
  const res = await getWithRetry(url.toString(), headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { cases, hasMore, nextCursor, nextId }
}
