// frontend/src/lib/connectivity.js
// True server reachability probe — replaces naive navigator.onLine checks.
// navigator.onLine only checks for a local interface connection, not backend reachability.
// In rural clinics with satellite internet, the local Wi-Fi can be up while the backend
// is unreachable — navigator.onLine stays true but all fetches hang for 60-90 seconds.

import { apiBase } from '@/api/base'

const PROBE_TIMEOUT_MS = 5000
const LEGACY_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function probeUrl(url, signal) {
  if (!url) return false
  try {
    const res = await fetch(`${url}/api/health`, {
      method: 'GET',
      cache: 'no-store',
      signal,
    })
    return res.ok
  } catch {
    return false
  }
}

/**
 * True connectivity check: verifies the VitalNet backend is reachable.
 * Dual-probe logic: probes the primary resolved health URL (e.g. edge),
 * and if that fails or is unreachable, falls back to probing the legacy backend.
 * Returns true if either backend responds within the 5-second timeout.
 *
 * Uses AbortController — no hanging fetch.
 * Uses cache:'no-store' — bypasses service worker cache.
 *
 * @returns {Promise<boolean>}
 */
export async function isServerReachable() {
  // Fast-path: no local network interface at all
  if (!navigator.onLine) return false

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)

  try {
    const primaryBase = apiBase('health')
    const primaryOk = await probeUrl(primaryBase, controller.signal)
    if (primaryOk) return true

    // Fallback: If primary target (e.g. edge) failed, probe legacy backend if distinct.
    // Note: When VITE_EDGE_API_BASE_URL is unset in local/dev environments,
    // apiBase('health') already evaluates to LEGACY_BASE, so primaryBase === LEGACY_BASE.
    // In that configuration, this fallback check is cleanly skipped (no redundant second probe).
    if (LEGACY_BASE && LEGACY_BASE !== primaryBase && !controller.signal.aborted) {
      const fallbackOk = await probeUrl(LEGACY_BASE, controller.signal)
      if (fallbackOk) return true
    }

    return false
  } catch {
    return false // AbortError (timeout), network error, or fetch failure
  } finally {
    clearTimeout(timeout)
  }
}

