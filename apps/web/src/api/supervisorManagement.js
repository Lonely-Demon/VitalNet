/**
 * supervisorManagement.js — Dedicated API wrappers for Supervisor governance endpoints.
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'
import { apiBase } from '@/api/base'

async function parseResponse(res) {
  if (!res.ok) {
    let message = res.statusText
    try {
      const json = await res.json()
      if (json && json.detail) {
        message = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail)
      }
    } catch {
      // fallback
    }
    throw new Error(message)
  }
  return res.json()
}

export async function supervisorListFacilities() {
  const headers = await authHeaders()
  const res = await getWithRetry(`${apiBase('supervisor.management')}/api/supervisor/management/facilities`, headers)
  return parseResponse(res)
}

export async function supervisorCreateFacility(data) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('supervisor.management')}/api/supervisor/management/facilities`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })
  return parseResponse(res)
}

export async function supervisorToggleFacility(facilityId) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('supervisor.management')}/api/supervisor/management/facilities/${facilityId}/toggle`, {
    method: 'PATCH',
    headers,
  })
  return parseResponse(res)
}

export async function supervisorListAdmins(page = 1, limit = 100) {
  const headers = await authHeaders()
  const res = await getWithRetry(
    `${apiBase('supervisor.management')}/api/supervisor/management/admins?page=${page}&limit=${limit}`,
    headers
  )
  return parseResponse(res)
}

export async function supervisorCreateAdmin(data) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('supervisor.management')}/api/supervisor/management/admins`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })
  return parseResponse(res)
}

export async function supervisorUpdateAdmin(userId, data) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('supervisor.management')}/api/supervisor/management/admins/${userId}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(data),
  })
  return parseResponse(res)
}

export async function supervisorDeactivateAdmin(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('supervisor.management')}/api/supervisor/management/admins/${userId}/deactivate`, {
    method: 'POST',
    headers,
  })
  return parseResponse(res)
}

export async function supervisorReactivateAdmin(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${apiBase('supervisor.management')}/api/supervisor/management/admins/${userId}/reactivate`, {
    method: 'POST',
    headers,
  })
  return parseResponse(res)
}
