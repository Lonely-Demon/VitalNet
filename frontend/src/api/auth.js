/**
 * auth.js — Stateless Supabase auth helpers.
 * No state stored here; all auth helpers are pure functions.
 */
import { v4 as uuidv4 } from 'uuid'
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
    deviceId = uuidv4()
    localStorage.setItem(DEVICE_ID_KEY, deviceId)
  }
  return deviceId
}

/**
 * Standard header shape for an already-known access token. Exported so
 * callers holding their own session (e.g. syncStore.js, which fetches and
 * null-checks the session itself) don't need to re-fetch it via authHeaders().
 */
export function buildAuthHeaders(token) {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'X-Device-Id': getDeviceId(),
    'X-CSRF-Token': 'vitalnet-spa',
  }
}

/**
 * Returns standard auth headers for API requests.
 * Throws if the user is not authenticated.
 */
export async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return buildAuthHeaders(session.access_token)
}
