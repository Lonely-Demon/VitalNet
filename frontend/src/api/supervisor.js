/**
 * supervisor.js — Stateless API wrappers for the supervisor team-metrics endpoint.
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function getTeamMetrics({ days, facilityId } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/supervisor/team-metrics`)
  if (days) url.searchParams.set('days', days)
  if (facilityId) url.searchParams.set('facility_id', facilityId)
  const res = await getWithRetry(url.toString(), headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
