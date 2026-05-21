/**
 * admin.js — Stateless API wrappers for all admin endpoints.
 *
 * Reliability improvements (ROOT-CHAOS-003):
 * - Centralized timeout wrapper (10s reads, 30s writes)
 * - Retry logic with exponential backoff
 */
import { authHeaders } from "@/api/auth";
import { fetchWithRetry } from "./retry";

const BASE = import.meta.env.VITE_API_BASE_URL;

// Timeouts for admin operations (ms)
const ADMIN_READ_TIMEOUT_MS = 10000;
const ADMIN_WRITE_TIMEOUT_MS = 30000;

// ── Users ─────────────────────────────────────────────────────────────────────

export async function adminListUsers() {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/users`,
		{ headers },
		{ timeoutMs: ADMIN_READ_TIMEOUT_MS, maxRetries: 2 },
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function adminCreateUser(data) {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/users`,
		{ method: "POST", headers, body: JSON.stringify(data) },
		{ timeoutMs: ADMIN_WRITE_TIMEOUT_MS, maxRetries: 0 }, // No retry for POST - idempotency concerns
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function adminUpdateUser(userId, data) {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/users/${userId}`,
		{ method: "PATCH", headers, body: JSON.stringify(data) },
		{ timeoutMs: ADMIN_WRITE_TIMEOUT_MS, maxRetries: 2 },
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function adminDeactivateUser(userId) {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/users/${userId}`,
		{ method: "DELETE", headers },
		{ timeoutMs: ADMIN_WRITE_TIMEOUT_MS, maxRetries: 2 },
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function adminReactivateUser(userId) {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/users/${userId}/reactivate`,
		{ method: "POST", headers },
		{ timeoutMs: ADMIN_WRITE_TIMEOUT_MS, maxRetries: 2 },
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

// ── Facilities ────────────────────────────────────────────────────────────────

export async function adminListFacilities() {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/facilities`,
		{ headers },
		{ timeoutMs: ADMIN_READ_TIMEOUT_MS, maxRetries: 2 },
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function adminCreateFacility(data) {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/facilities`,
		{ method: "POST", headers, body: JSON.stringify(data) },
		{ timeoutMs: ADMIN_WRITE_TIMEOUT_MS, maxRetries: 0 }, // No retry for POST - idempotency concerns
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function adminToggleFacility(facilityId) {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/facilities/${facilityId}/toggle`,
		{ method: "PATCH", headers },
		{ timeoutMs: ADMIN_WRITE_TIMEOUT_MS, maxRetries: 2 },
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export async function adminGetStats() {
	const headers = await authHeaders();
	const res = await fetchWithRetry(
		`${BASE}/api/admin/stats`,
		{ headers },
		{ timeoutMs: ADMIN_READ_TIMEOUT_MS, maxRetries: 2 },
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}
