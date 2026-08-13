// Ported from app/api/routes/security.py — case soft-delete. Kept as its
// own route module (rather than folded into cases.ts) since it's the one
// write path scoped to requireRole across all three roles plus a mandatory
// device-binding header, distinct from cases.ts's per-role endpoints.
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { extractBearerToken, getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { AuditEventType, getClientIp, logPhiAccess } from "../_shared/audit.ts";
import { fetchAuthorizedCase, parseUuid } from "../_shared/cases.ts";
import type { AppEnv } from "../_shared/types.ts";

export const security = new Hono<AppEnv>();

security.delete(
  "/api/security/cases/:case_id",
  rateLimit(30, 60),
  requireRole("admin", "doctor", "asha_worker"),
  async (c) => {
    const user = c.get("user");
    const deviceId = c.req.header("X-Device-Id");
    if (!deviceId) {
      throw new HttpError(400, "Missing device binding header");
    }

    const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
    const rawToken = extractBearerToken(c.req.header("authorization"));
    const db = getSupabaseForUser(rawToken);

    const row = await fetchAuthorizedCase(db, caseUuid, user);

    const { data: updated, error } = await db
      .from("case_records")
      .update({ deleted_at: new Date().toISOString() })
      .eq("id", caseUuid)
      .is("deleted_at", null)
      .select();
    if (error) throw error;
    if (!updated || updated.length === 0) {
      throw new HttpError(409, "Case could not be deleted or already deleted");
    }

    await logPhiAccess({
      eventType: AuditEventType.PHI_DELETE,
      userId: user.sub ?? "unknown",
      userRole: user.resolvedRole,
      resourceType: "case_records",
      resourceId: caseUuid,
      facilityId: row.facility_id,
      ipAddress: getClientIp(c),
      details: { device_id: deviceId },
    });

    return c.json({ status: "deleted", case_id: caseUuid });
  },
);
