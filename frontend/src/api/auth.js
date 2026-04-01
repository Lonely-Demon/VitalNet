/**
 * auth.js — Stateless Supabase auth helpers.
 * No state stored here; all auth helpers are pure functions.
 */
import { supabase } from '@/lib/supabase'

/**
 * Returns standard auth headers for API requests.
 * Throws if the user is not authenticated.
 */
export async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  const deviceId = getOrCreateDeviceId()
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session.access_token}`,
    'X-Device-Id': deviceId,
    'X-CSRF-Token': import.meta.env.VITE_CSRF_TOKEN || 'vitalnet-spa',
  }
}

function getOrCreateDeviceId() {
  const key = 'vitalnet_device_id'
  let value = localStorage.getItem(key)
  if (!value) {
    value = globalThis.crypto?.randomUUID?.() || `dev-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    localStorage.setItem(key, value)
  }
  return value
}
