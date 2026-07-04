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

export async function getEmergencyRate() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${BASE}/api/analytics/emergency-rate`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
