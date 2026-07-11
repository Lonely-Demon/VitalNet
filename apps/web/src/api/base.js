/**
 * base.js — Per-endpoint API base-URL resolver (Round 6 rebuild plan,
 * Phase 3 "frontend cutover map").
 *
 * During the strangler-fig migration two backends serve the same /api/...
 * contract: the legacy FastAPI backend (VITE_API_BASE_URL) and the new
 * Supabase Edge Function (VITE_EDGE_API_BASE_URL — typically
 * https://<project>.supabase.co/functions/v1/api). This map decides, per
 * endpoint, which one a given call goes to — so cutting an endpoint over
 * is a one-line flip here, and rolling it back is reverting that line.
 * Nothing else in the calling code changes.
 *
 * Rules:
 *  - Only endpoints that EXIST in apps/api may be flipped to 'edge' —
 *    the keys below are exactly the Tranche A surface; Tranche B
 *    endpoints keep their plain VITE_API_BASE_URL until ported.
 *  - Everything defaults to 'legacy'. If VITE_EDGE_API_BASE_URL is unset,
 *    'edge' entries silently fall back to legacy too (safe in local dev).
 */

const LEGACY_BASE = import.meta.env.VITE_API_BASE_URL
const EDGE_BASE = import.meta.env.VITE_EDGE_API_BASE_URL || ''

// One key per ported endpoint. Flip 'legacy' -> 'edge' to cut over.
const ENDPOINT_BACKEND = {
  'health': 'legacy',
  'outbreak.signals': 'legacy',
  'supervisor.teamMetrics': 'legacy',
  'referrals.listFacilities': 'legacy',
  'referrals.list': 'legacy',
  'metrics': 'legacy',
  'protocol.listQuestions': 'legacy',
  'analytics.summary': 'legacy',
  'analytics.emergencyRate': 'legacy',
  'analytics.responseTimes': 'legacy',
  'analytics.mlAgreement': 'legacy',
  'analytics.export': 'legacy',
}

/**
 * Returns the base URL to use for `endpoint` (one of the keys above).
 * Unknown endpoints — including every not-yet-ported Tranche B endpoint —
 * always resolve to the legacy backend.
 */
export function apiBase(endpoint) {
  const target = ENDPOINT_BACKEND[endpoint] ?? 'legacy'
  return target === 'edge' && EDGE_BASE ? EDGE_BASE : LEGACY_BASE
}
