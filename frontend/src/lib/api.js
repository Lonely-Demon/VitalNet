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
