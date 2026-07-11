// Ported from app/api/routes/dsr_routes.py — DPDP Act 2023 data-subject-
// request (DSR) lifecycle (docs/COMPLIANCE_DPDP.md). Admin-mediated
// because the patient is not a VitalNet user — there's no login for a
// patient to request their own export, so a facility admin acts on a
// verified in-person/offline request. Uses getSupabaseAdmin() throughout
// (service-role), same as the Python original's supabase_admin usage —
// this is a legitimate admin-only exception, not a narrow-aggregate one
// (see _shared/database.ts's header).
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseAdmin, HttpError } from "../_shared/database.ts";
import { getConfig } from "../_shared/config.ts";
import { AuditEventType, getClientIp, logPhiAccess } from "../_shared/audit.ts";
import { parseUuid } from "../_shared/cases.ts";
import type { AppEnv } from "../_shared/types.ts";

export const dsr = new Hono<AppEnv>();

const REDACTED = "[REDACTED — see docs/COMPLIANCE_DPDP.md]";

// Direct-identifier / free-text fields on case_records that plausibly carry
// patient-identifying content. Vitals, symptom codes, triage outputs, and
// timestamps are left intact — they're the de-identified clinical signal
// the retraining/aggregate-reporting use case depends on.
const ERASABLE_CASE_FIELDS = [
  "patient_name",
  "patient_location",
  "chief_complaint",
  "observations",
  "known_conditions",
  "current_medications",
] as const;

interface CaseRecord {
  id: string;
  facility_id: string | null;
  deleted_at: string | null;
  [key: string]: unknown;
}

async function fetchCaseOr404(caseUuid: string): Promise<CaseRecord> {
  const { data, error } = await getSupabaseAdmin()
    .from("case_records")
    .select("*")
    .eq("id", caseUuid)
    .maybeSingle();
  if (error) throw error;
  if (!data) throw new HttpError(404, "Case not found");
  return data as CaseRecord;
}

dsr.get("/api/admin/cases/:case_id/export", rateLimit(10, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
  const admin = getSupabaseAdmin();

  const caseRecord = await fetchCaseOr404(caseUuid);

  const [outcomes, attachments, referrals] = await Promise.all([
    admin.from("case_outcomes").select("*").eq("case_id", caseUuid),
    admin.from("case_attachments").select("*").eq("case_id", caseUuid),
    admin.from("referrals").select("*").eq("case_id", caseUuid),
  ]);
  if (outcomes.error) throw outcomes.error;
  if (attachments.error) throw attachments.error;
  if (referrals.error) throw referrals.error;

  await logPhiAccess({
    eventType: AuditEventType.PHI_EXPORT,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "case_records",
    resourceId: caseUuid,
    facilityId: caseRecord.facility_id,
    ipAddress: getClientIp(c),
    details: {
      reason: "data_subject_request",
      tables: ["case_records", "case_outcomes", "case_attachments", "referrals"],
    },
  });

  return c.json({
    case_id: caseUuid,
    exported_at: new Date().toISOString(),
    case: caseRecord,
    outcomes: outcomes.data ?? [],
    attachments: attachments.data ?? [],
    referrals: referrals.data ?? [],
  });
});

/**
 * Anonymises rather than hard-deletes: identifying free-text fields on
 * case_records and referrals.reason are replaced with a redaction marker,
 * and the case is soft-deleted if not already. case_outcomes is
 * deliberately left untouched — an immutable, insert-only table by design
 * that carries no direct patient identifier.
 */
async function eraseCaseRow(caseUuid: string, caseRecord: CaseRecord): Promise<void> {
  const admin = getSupabaseAdmin();
  const updateBody: Record<string, string> = {};
  for (const field of ERASABLE_CASE_FIELDS) updateBody[field] = REDACTED;
  if (caseRecord.deleted_at === null) {
    (updateBody as Record<string, unknown>).deleted_at = new Date().toISOString();
  }

  const { error: caseError } = await admin.from("case_records").update(updateBody).eq("id", caseUuid);
  if (caseError) throw caseError;

  const { error: referralError } = await admin.from("referrals").update({ reason: REDACTED }).eq(
    "case_id",
    caseUuid,
  );
  if (referralError) throw referralError;
}

dsr.post("/api/admin/cases/:case_id/erase", rateLimit(10, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");

  const caseRecord = await fetchCaseOr404(caseUuid);
  await eraseCaseRow(caseUuid, caseRecord);

  await logPhiAccess({
    eventType: AuditEventType.PHI_ERASURE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "case_records",
    resourceId: caseUuid,
    facilityId: caseRecord.facility_id,
    ipAddress: getClientIp(c),
    details: { reason: "data_subject_request", redacted_fields: ERASABLE_CASE_FIELDS },
  });

  return c.json({ status: "erased", case_id: caseUuid, redacted_fields: ERASABLE_CASE_FIELDS });
});

dsr.post("/api/admin/cases/purge-expired", rateLimit(6, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const config = getConfig();

  if (config.dataRetentionDays <= 0) {
    return c.json({ enabled: false, purged: 0 });
  }

  const threshold = new Date(Date.now() - config.dataRetentionDays * 24 * 60 * 60 * 1000).toISOString();

  const { data: candidates, error } = await getSupabaseAdmin()
    .from("case_records")
    .select("id, facility_id, deleted_at")
    .lt("created_at", threshold)
    .neq("patient_name", REDACTED);
  if (error) throw error;

  const purged: string[] = [];
  for (const row of (candidates ?? []) as CaseRecord[]) {
    await eraseCaseRow(row.id, row);
    await logPhiAccess({
      eventType: AuditEventType.PHI_ERASURE,
      userId: user.sub ?? "unknown",
      userRole: user.resolvedRole,
      resourceType: "case_records",
      resourceId: row.id,
      facilityId: row.facility_id,
      ipAddress: getClientIp(c),
      details: { reason: "retention_policy_purge", redacted_fields: ERASABLE_CASE_FIELDS },
    });
    purged.push(row.id);
  }

  return c.json({ enabled: true, checked: (candidates ?? []).length, purged: purged.length });
});
