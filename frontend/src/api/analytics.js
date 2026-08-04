/**
 * analytics.js — Stateless API wrappers for analytics endpoints.
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function getAnalyticsSummary() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${BASE}/api/analytics/summary`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getResponseTimes() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${BASE}/api/analytics/response-times`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { tiers: { ROUTINE, URGENT, EMERGENCY } }
}

export async function getMlAgreement() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${BASE}/api/analytics/ml-agreement`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { overall_agreement_rate, overall_count, by_tier }
}

/**
 * Downloads a CSV of case records for the given date range (facility reporting,
 * FEATURES_ROADMAP §1b.3). Triggers a browser file download rather than
 * returning parsed data, since the endpoint streams a CSV file.
 */
export async function exportCases({ dateFrom, dateTo }) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/analytics/export`)
  url.searchParams.set('date_from', dateFrom)
  url.searchParams.set('date_to', dateTo)
  const res = await fetch(url.toString(), { headers })
  if (!res.ok) throw new Error(await res.text())

  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : 'vitalnet_cases.csv'

  const downloadUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = downloadUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(downloadUrl)
}
