/**
 * auth.js — Stateless Supabase auth helpers.
 * No state stored here; all auth helpers are pure functions.
 */
import { supabase } from '@/lib/supabase'

const DEVICE_ID_KEY = 'vn_device_id'

/**
 * Stable per-browser device identifier, persisted in localStorage. Sent as
 * X-Device-Id on every mutating request (see main.py's csrf_and_device_guard)
 * for future abuse/anomaly detection — not a security boundary by itself.
 */
export function getDeviceId() {
  let deviceId = localStorage.getItem(DEVICE_ID_KEY)
  if (!deviceId) {
    deviceId = typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, c =>
          (+c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (+c / 4)))).toString(16)
        )
    localStorage.setItem(DEVICE_ID_KEY, deviceId)
  }
  return deviceId
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
    'X-Device-Id': getDeviceId(),
    'X-CSRF-Token': 'vitalnet-spa',
  }
}
