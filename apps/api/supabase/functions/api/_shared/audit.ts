// Ported from app/core/audit.py — PHI audit logging. Every create/read/
// update/delete of patient case data is logged with who/what/when/where.
// Writes to phi_audit_log using getSupabaseAdmin() (service-role) — one
// of the two remaining legitimate service-role uses per database.ts'
// header comment. Best-effort: a DB write failure is logged but never
// thrown, so a transient DB blip can't break the request it's attached to.
//
// Never log patient free-text or vitals here — only identifiers
// (user/resource IDs, facility, role, IP) and coarse action metadata.
import type { Context } from "hono";
import { getSupabaseAdmin } from "./database.ts";

export const AuditEventType = {
  PHI_CREATE: "PHI_CREATE",
  PHI_READ: "PHI_READ",
  PHI_UPDATE: "PHI_UPDATE",
  PHI_DELETE: "PHI_DELETE",
  PHI_EXPORT: "PHI_EXPORT",
  PHI_ERASURE: "PHI_ERASURE",
  AUTH_LOGIN: "AUTH_LOGIN",
  AUTH_LOGOUT: "AUTH_LOGOUT",
  AUTH_FAILED: "AUTH_FAILED",
  CONSENT_CAPTURED: "CONSENT_CAPTURED",
} as const;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** phi_audit_log.user_id/facility_id are uuid columns — some call sites
 * pass placeholder strings like "unknown" when a real id isn't available.
 * Insert NULL rather than let a non-UUID string fail the whole insert. */
function asUuidOrNull(value: string | null | undefined): string | null {
  if (!value) return null;
  return UUID_RE.test(value) ? value : null;
}

export interface LogPhiAccessInput {
  eventType: string;
  userId: string;
  resourceType: string;
  resourceId?: string | null;
  facilityId?: string | null;
  ipAddress?: string | null;
  userRole?: string | null;
  details?: Record<string, unknown>;
}

export async function logPhiAccess(input: LogPhiAccessInput): Promise<void> {
  const {
    eventType,
    userId,
    resourceType,
    resourceId = null,
    facilityId = null,
    ipAddress = null,
    userRole = null,
    details = {},
  } = input;

  // Intentional: this IS the PHI access audit trail. Recording who/what/
  // when/where in plain, greppable structured logs is the entire point of
  // an audit log; only coarse identifiers are logged (never patient
  // free-text/vitals).
  console.info(
    `event=${eventType} user=${userId} role=${userRole} resource=${resourceType}:${resourceId} facility=${facilityId} ip=${ipAddress} details=${
      JSON.stringify(details)
    }`,
  );

  try {
    const { error } = await getSupabaseAdmin().from("phi_audit_log").insert({
      event_type: eventType,
      user_id: asUuidOrNull(userId),
      user_role: userRole,
      resource_type: resourceType,
      resource_id: resourceId,
      facility_id: asUuidOrNull(facilityId),
      ip_address: ipAddress,
      details,
    });
    if (error) throw error;
  } catch (e) {
    console.warn("Failed to persist audit log entry to phi_audit_log:", e);
  }
}

/** Extract the client IP, preferring proxy headers. */
export function getClientIp(c: Context): string {
  const forwarded = c.req.header("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0]!.trim();
  const realIp = c.req.header("x-real-ip");
  if (realIp) return realIp;
  return "unknown";
}
