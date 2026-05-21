// frontend/src/lib/connectivity.js
// True server reachability probe — replaces naive navigator.onLine checks.
// navigator.onLine only checks for a local interface connection, not backend reachability.
// In rural clinics with satellite internet, the local Wi-Fi can be up while the backend
// is unreachable — navigator.onLine stays true but all fetches hang for 60-90 seconds.

const PROBE_TIMEOUT_MS = 5000
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const PROBE_URL = API_BASE ? `${API_BASE}/api/health` : '/api/health'
// This correctly handles deployments where the backend is on the clinic LAN.

/**
 * True connectivity check: verifies the VitalNet backend is reachable.
 * Returns true only if /api/health responds within 5 seconds.
 *
 * Uses AbortController — no hanging fetch.
 * Uses cache:'no-store' — bypasses service worker cache (a cached SW response
 * would make the probe succeed while fully offline).
 *
 * @returns {Promise<boolean>}
 */
export async function isServerReachable() {
  // Fast-path: no local network interface at all
  if (!navigator.onLine) return false

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)

  try {
    const res = await fetch(PROBE_URL, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    })
    return res.ok
  } catch {
    return false   // AbortError (timeout), network error, or fetch failure
  } finally {
    clearTimeout(timeout)
  }
}
