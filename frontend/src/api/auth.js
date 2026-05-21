/**
 * auth.js — Stateless Supabase auth helpers.
 * No state stored here; all auth helpers are pure functions.
 */
import { supabase } from '@/lib/supabase'

// Initialize stable device UUID
let deviceId = localStorage.getItem('vn_device_id')
if (!deviceId) {
  if (typeof crypto.randomUUID === 'function') {
    deviceId = crypto.randomUUID()
  } else {
    deviceId = '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, c =>
      (+c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> +c / 4).toString(16)
    )
  }
  localStorage.setItem('vn_device_id', deviceId)
}

/**
 * Returns standard auth headers for API requests.
 * Throws if the user is not authenticated.
 */
export async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session.access_token}`,
    'X-Device-Id': deviceId,
    'X-CSRF-Token': 'vitalnet-spa',
  }
}
