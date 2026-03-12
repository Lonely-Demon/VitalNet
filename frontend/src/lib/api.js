import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_BASE_URL

async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return {
    'Content-Type':  'application/json',
    'Authorization': `Bearer ${session.access_token}`,
  }
}

export async function submitCase(formData) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/submit`, {
    method:  'POST',
    headers,
    body:    JSON.stringify(formData),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getCases() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function reviewCase(caseId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/${caseId}/review`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Users ──────────────────────────────────────────────────────────────

export async function adminListUsers() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateUser(data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminUpdateUser(userId, data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}`, {
    method: 'PATCH', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminDeactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminReactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}/reactivate`, {
    method: 'POST', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Facilities ─────────────────────────────────────────────────────────

export async function adminListFacilities() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateFacility(data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminToggleFacility(facilityId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities/${facilityId}/toggle`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Stats ──────────────────────────────────────────────────────────────

export async function adminGetStats() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/stats`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── ASHA: Submission history ──────────────────────────────────────────────────

export async function getMySubmissions() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/mine`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
