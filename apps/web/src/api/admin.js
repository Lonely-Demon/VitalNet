/**
 * admin.js — Stateless API wrappers for all admin endpoints.
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'
import { apiBase } from '@/api/base'

// ── Users ─────────────────────────────────────────────────────────────────────

export async function adminListUsers() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${apiBase('admin.users')}/api/admin/users`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateUser(data) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('admin.users')}/api/admin/users`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminUpdateUser(userId, data) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('admin.users')}/api/admin/users/${userId}`, {
    method: 'PATCH', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminDeactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('admin.users')}/api/admin/users/${userId}`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminReactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('admin.users')}/api/admin/users/${userId}/reactivate`, {
    method: 'POST', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/** Bulk ASHA/doctor onboarding via CSV import (FEATURES_ROADMAP §1b.4). */
export async function adminBulkCreateUsers(users) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('admin.users')}/api/admin/users/bulk`, {
    method: 'POST', headers, body: JSON.stringify({ users }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { results, succeeded, failed }
}

// ── Facilities ────────────────────────────────────────────────────────────────

export async function adminListFacilities() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${apiBase('admin.facilities')}/api/admin/facilities`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateFacility(data) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('admin.facilities')}/api/admin/facilities`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminToggleFacility(facilityId) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('admin.facilities')}/api/admin/facilities/${facilityId}/toggle`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export async function adminGetStats() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${apiBase('admin.stats')}/api/admin/stats`, headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Audit Log ─────────────────────────────────────────────────────────────────

export async function adminGetAuditLog({ before } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${apiBase('admin.auditLog')}/api/admin/audit-log`)
  if (before) url.searchParams.set('before', before)
  url.searchParams.set('limit', '50')
  const res = await getWithRetry(url.toString(), headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()   // Returns { entries, hasMore, nextCursor }
}
