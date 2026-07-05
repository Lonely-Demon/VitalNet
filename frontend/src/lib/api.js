/**
 * api.js — Backward-compatible re-export barrel.
 *
 * The monolithic api.js has been decomposed into domain-specific modules:
 *   - @/api/auth.js       → authHeaders
 *   - @/api/cases.js      → getCases, reviewCase, getMySubmissions, overrideTriage, recordCaseOutcome, getPatientSummary, getCaseHistoryByPatientKey
 *   - @/api/admin.js      → adminList/Create/Update/Deactivate/Reactivate users + facilities + stats
 *   - @/api/analytics.js  → getAnalyticsSummary, getEmergencyRate
 *   - @/api/supervisor.js → getTeamMetrics
 *   - @/api/outbreak.js   → getOutbreakSignals
 *   - @/stores/syncStore.js → submitCase, processQueue (stateful offline queue manager)
 *
 * This barrel keeps existing consumers working without requiring immediate refactors.
 * Migrate direct imports to the domain files above at your convenience.
 */

export { authHeaders } from '@/api/auth'
export { submitCase, processQueue } from '@/stores/syncStore'
export { getCases, reviewCase, getMySubmissions, overrideTriage, recordCaseOutcome, getPatientSummary, getCaseHistoryByPatientKey } from '@/api/cases'
export {
  adminListUsers,
  adminCreateUser,
  adminUpdateUser,
  adminDeactivateUser,
  adminReactivateUser,
  adminBulkCreateUsers,
  adminListFacilities,
  adminCreateFacility,
  adminToggleFacility,
  adminGetStats,
  adminGetAuditLog,
} from '@/api/admin'
export { getAnalyticsSummary, getEmergencyRate, getResponseTimes, getMlAgreement, exportCases } from '@/api/analytics'
export { listActiveFacilities, createReferral, listReferrals, updateReferralStatus, updateFacilityCapacity } from '@/api/referrals'
export { getTeamMetrics } from '@/api/supervisor'
export { getOutbreakSignals } from '@/api/outbreak'
