/**
 * analytics.js — Stateless API wrappers for analytics endpoints.
 *
 * Reliability improvements (CHAOS-005 to CHAOS-010):
 * - Retry logic with exponential backoff for transient failures
 * - Timeout handling to prevent hanging requests
 * - Graceful degradation support (handles degraded responses)
 */
import { authHeaders } from '@/api/auth'
import { fetchWithRetry } from './retry'

const BASE = import.meta.env.VITE_API_BASE_URL

// Timeout for analytics requests (ms)
const ANALYTICS_TIMEOUT_MS = 15000

export async function getAnalyticsSummary() {
  const headers = await authHeaders()
  try {
    const res = await fetchWithRetry(
      `${BASE}/api/analytics/summary`,
      { headers },
      { timeoutMs: ANALYTICS_TIMEOUT_MS, maxRetries: 2 }
    )
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()

    // Handle degraded response (partial data)
    if (data._degraded) {
      console.warn('[Analytics] Summary returned degraded data:', data._failed_queries)
    }

    return data
  } catch (error) {
    // Return graceful degradation fallback structure
    console.error('[Analytics] Summary fetch failed:', error.message)
    return {
      total_cases: 0,
      triage_distribution: { ROUTINE: 0, URGENT: 0, EMERGENCY: 0 },
      daily_volume: {},
      reviewed_count: 0,
      unreviewed_count: 0,
      top_asha_workers: [],
      _error: error.message,
      _fallback: true,
    }
  }
}

export async function getEmergencyRate() {
  const headers = await authHeaders()
  try {
    const res = await fetchWithRetry(
      `${BASE}/api/analytics/emergency-rate`,
      { headers },
      { timeoutMs: ANALYTICS_TIMEOUT_MS, maxRetries: 2 }
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  } catch (error) {
    // Return graceful degradation fallback structure
    console.error('[Analytics] Emergency rate fetch failed:', error.message)
    return {
      weeks: [],
      _error: error.message,
      _fallback: true,
    }
  }
}
