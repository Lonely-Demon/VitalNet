/**
 * outbreak.js — Stateless API wrapper for the outbreak-signals endpoint.
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'
import { apiBase } from '@/api/base'

export async function getOutbreakSignals({ facilityId } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${apiBase('outbreak.signals')}/api/outbreak/signals`)
  if (facilityId) url.searchParams.set('facility_id', facilityId)
  const res = await getWithRetry(url.toString(), headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
