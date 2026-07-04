/**
 * referrals.js — Stateless API wrappers for the inter-facility referral
 * workflow (FEATURES_ROADMAP §2.3).
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function listActiveFacilities() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${BASE}/api/facilities`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function createReferral(caseId, { receiving_facility_id, reason, urgency }) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/${caseId}/refer`, {
    method: 'POST', headers,
    body: JSON.stringify({ receiving_facility_id, reason, urgency }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listReferrals({ direction = 'all' } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/referrals`)
  url.searchParams.set('direction', direction)
  const res = await getWithRetry(url.toString(), headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { referrals }
}

export async function updateReferralStatus(referralId, status) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/referrals/${referralId}/status`, {
    method: 'PATCH', headers,
    body: JSON.stringify({ status }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
