// Ported from referral_routes.py — includes read-only endpoints (Tranche A)
// and write endpoints: facility capacity PATCH, create referral POST,
// advance-status PATCH (Tranche B / ADR §53).
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { type Facility, mergeOpenCaseCounts, type OpenCaseCountRow } from "../_shared/facilities.ts";
import { parseUuid } from "../_shared/cases.ts";
import { AuditEventType, getClientIp, logPhiAccess } from "../_shared/audit.ts";
import type { AppEnv } from "../_shared/types.ts";

export const referral = new Hono<AppEnv>();

export const SBAR_VERSION = "sbar.v1";

// Forward-only state machine; 'cancelled' is reachable from any active state.
const ALLOWED_TRANSITIONS: Record<string, Set<string>> = {
  pending: new Set(["acknowledged", "cancelled"]),
  acknowledged: new Set(["patient_arrived", "cancelled"]),
  patient_arrived: new Set(["completed", "cancelled"]),
  completed: new Set(),
  cancelled: new Set(),
};

const REFERRAL_SELECT_COLUMNS = "id, case_id, referred_by, referring_facility_id, receiving_facility_id, " +
  "reason, urgency, sbar_version, sbar_draft, status, created_at, updated_at, " +
  "case_records(chief_complaint, patient_age, patient_sex, triage_level), " +
  "referring_facility:facilities!referring_facility_id(name), " +
  "receiving_facility:facilities!receiving_facility_id(name)";

function sbarValue(val: unknown, fallback = "Not recorded"): string {
  if (val === null || val === undefined || val === "" || (Array.isArray(val) && val.length === 0)) {
    return fallback;
  }
  return String(val);
}

function sbarVitals(caseRow: Record<string, unknown>): string {
  const values: string[] = [];
  if (
    caseRow.bp_systolic !== null && caseRow.bp_systolic !== undefined &&
    caseRow.bp_diastolic !== null && caseRow.bp_diastolic !== undefined
  ) {
    values.push(`BP ${caseRow.bp_systolic}/${caseRow.bp_diastolic} mmHg`);
  } else if (caseRow.bp_systolic !== null && caseRow.bp_systolic !== undefined) {
    values.push(`BP ${caseRow.bp_systolic} mmHg`);
  }
  if (caseRow.spo2 !== null && caseRow.spo2 !== undefined) {
    values.push(`SpO₂ ${caseRow.spo2} %`);
  }
  if (caseRow.heart_rate !== null && caseRow.heart_rate !== undefined) {
    values.push(`Heart rate ${caseRow.heart_rate} bpm`);
  }
  if (caseRow.temperature !== null && caseRow.temperature !== undefined) {
    values.push(`Temperature ${caseRow.temperature} °C`);
  }
  return values.length > 0 ? values.join("; ") : "No vital signs recorded";
}

export function buildSbar(
  caseRow: Record<string, unknown>,
  referralInput: { reason?: unknown; urgency?: unknown },
): string {
  const symptoms = (caseRow.symptoms as unknown[]) || [];
  const symptomText = symptoms.length > 0
    ? symptoms.map((item) => String(item)).join(", ")
    : "No structured symptoms recorded";
  const flags = (caseRow.contraindication_flags as unknown[]) || [];
  const flagText = flags.length > 0 ? flags.map((item) => String(item)).join("; ") : "None recorded";
  const triage = sbarValue(caseRow.triage_level);
  const urgency = sbarValue(referralInput.urgency);
  const reason = sbarValue(referralInput.reason);

  return [
    "SITUATION",
    `Patient age: ${sbarValue(caseRow.patient_age, "Not recorded")} years; sex: ${sbarValue(caseRow.patient_sex)}.`,
    `Presenting problem: ${sbarValue(caseRow.chief_complaint)}.`,
    `Stored VitalNet triage tier: ${triage} (clinician verification required).`,
    "",
    "BACKGROUND",
    `Complaint duration: ${sbarValue(caseRow.complaint_duration)}.`,
    `Known conditions: ${sbarValue(caseRow.known_conditions)}.`,
    `Current medications: ${sbarValue(caseRow.current_medications)}.`,
    `Structured symptoms: ${symptomText}.`,
    "",
    "ASSESSMENT",
    `Recorded vital signs: ${sbarVitals(caseRow)}.`,
    `Stored risk driver: ${sbarValue(caseRow.risk_driver)}.`,
    `Recorded contraindication flags: ${flagText}.`,
    `Deterioration alert recorded: ${caseRow.deterioration_alert ? "Yes" : "No"}.`,
    "This section reports recorded data only; it does not establish a diagnosis.",
    "",
    "RECOMMENDATION / REQUEST",
    `Referral urgency selected by clinician: ${urgency}.`,
    `Referral reason: ${reason}.`,
    "Please acknowledge receipt and complete local clinical assessment on arrival.",
  ].join("\n");
}

// ── Facility picker (for the referral target dropdown) ─────────────────────

referral.get("/api/facilities", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const db = getSupabaseForUser(user.token);

  let query = db
    .from("facilities")
    .select("id, name, type, district, capacity_status")
    .eq("is_active", true)
    .order("name");
  if (user.resolvedFacilityId) {
    query = query.neq("id", user.resolvedFacilityId);
  }

  const { data: facilities, error: facilitiesError } = await query;
  if (facilitiesError) {
    console.warn("Facilities query failed:", facilitiesError);
    throw new HttpError(502, "Facilities query failed — try again");
  }

  // Open (unreviewed) case load per facility — see fn_open_case_counts'
  // header comment (phase28_security_definer_fns.sql) for why this calls
  // the caller's own RLS-scoped client, not a service-role client.
  const { data: openCounts, error: countsError } = await db.rpc("fn_open_case_counts", {});
  if (countsError) {
    console.warn("Open case counts query failed:", countsError);
    throw new HttpError(502, "Facilities query failed — try again");
  }

  let callerDistrict: string | null = null;
  if (user.resolvedFacilityId) {
    try {
      const { data: callerFac } = await db
        .from("facilities")
        .select("district")
        .eq("id", user.resolvedFacilityId)
        .maybeSingle();
      if (callerFac && callerFac.district) {
        callerDistrict = callerFac.district;
      }
    } catch (e) {
      console.debug("Could not resolve caller facility district:", e);
    }
  }

  const merged = mergeOpenCaseCounts(
    (facilities ?? []) as Facility[],
    (openCounts ?? []) as OpenCaseCountRow[],
    callerDistrict,
  );
  return c.json(merged);
});

interface CaseReferralRow {
  id: string;
  facility_id: string | null;
  deleted_at: string | null;
  patient_age: number | null;
  patient_sex: string | null;
  chief_complaint: string | null;
  complaint_duration: string | null;
  known_conditions: string | null;
  current_medications: string | null;
  symptoms: unknown[] | null;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  spo2: number | null;
  heart_rate: number | null;
  temperature: number | null;
  triage_level: string | null;
  risk_driver: string | null;
  contraindication_flags: unknown[] | null;
  deterioration_alert: boolean | null;
}

// ── Facility self-reported capacity ────────────────────────────────────────────

referral.patch(
  "/api/facilities/:facility_id/capacity",
  rateLimit(30, 60),
  requireRole("doctor", "admin"),
  async (c) => {
    const user = c.get("user");
    const facilityUuid = parseUuid(c.req.param("facility_id")!, "facility_id");
    const body = await c.req.json().catch(() => ({}));
    if (body.capacity_status !== "available" && body.capacity_status !== "limited" && body.capacity_status !== "full") {
      throw new HttpError(400, "capacity_status must be available, limited, or full");
    }

    if (user.resolvedRole !== "admin" && (!user.resolvedFacilityId || user.resolvedFacilityId !== facilityUuid)) {
      throw new HttpError(403, "Can only update your own facility's capacity");
    }

    const db = getSupabaseForUser(user.token);
    const { data, error } = await db
      .from("facilities")
      .update({
        capacity_status: body.capacity_status,
        capacity_updated_at: new Date().toISOString(),
      })
      .eq("id", facilityUuid)
      .select();

    if (error || !data || data.length === 0) {
      throw new HttpError(404, "Facility not found");
    }

    await logPhiAccess({
      eventType: AuditEventType.PHI_UPDATE,
      userId: user.sub ?? "unknown",
      userRole: user.resolvedRole,
      resourceType: "facilities",
      resourceId: facilityUuid,
      facilityId: facilityUuid,
      ipAddress: getClientIp(c),
      details: { capacity_status: body.capacity_status },
    });

    return c.json(data[0]);
  },
);

// ── Create referral ────────────────────────────────────────────────────────────

referral.post("/api/cases/:case_id/refer", rateLimit(20, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
  const body = await c.req.json().catch(() => ({}));
  const receivingFacilityUuid = parseUuid(body.receiving_facility_id, "receiving_facility_id");
  const reason = typeof body.reason === "string" ? body.reason.trim() : "";
  if (!reason || reason.length > 1000) {
    throw new HttpError(400, "Reason must be between 1 and 1000 characters");
  }
  const urgency = body.urgency;
  if (urgency !== "ROUTINE" && urgency !== "URGENT" && urgency !== "EMERGENCY") {
    throw new HttpError(400, "Urgency must be ROUTINE, URGENT, or EMERGENCY");
  }

  const db = getSupabaseForUser(user.token);
  const { data: rawCase, error: caseErr } = await db
    .from("case_records")
    .select(
      "id, facility_id, deleted_at, patient_age, patient_sex, chief_complaint, " +
        "complaint_duration, known_conditions, current_medications, symptoms, " +
        "bp_systolic, bp_diastolic, spo2, heart_rate, temperature, triage_level, " +
        "risk_driver, contraindication_flags, deterioration_alert",
    )
    .eq("id", caseUuid)
    .maybeSingle();

  const caseRow = rawCase as unknown as CaseReferralRow | null;
  if (caseErr || !caseRow || caseRow.deleted_at !== null) {
    throw new HttpError(404, "Case not found");
  }

  if (user.resolvedRole !== "admin" && (!user.resolvedFacilityId || user.resolvedFacilityId !== caseRow.facility_id)) {
    throw new HttpError(403, "Not authorized for this case");
  }

  const referringFacilityId = caseRow.facility_id;
  if (!referringFacilityId) {
    throw new HttpError(400, "Case has no facility to refer from");
  }
  if (receivingFacilityUuid === referringFacilityId) {
    throw new HttpError(400, "Cannot refer a case to its own facility");
  }

  // Deduplicate active referrals (BUG-36)
  try {
    const { data: existingActive } = await db
      .from("referrals")
      .select("id, status")
      .eq("case_id", caseUuid)
      .in("status", ["pending", "acknowledged", "patient_arrived"])
      .limit(1);

    if (existingActive && existingActive.length > 0) {
      const activeRef = existingActive[0]!;
      throw new HttpError(
        409,
        `An active referral already exists for this case (id: ${activeRef.id}, status: ${activeRef.status})`,
      );
    }
  } catch (e) {
    if (e instanceof HttpError) throw e;
    console.warn("Could not query existing active referrals:", e);
  }

  const sbarDraft = buildSbar(caseRow as unknown as Record<string, unknown>, { reason, urgency });

  const { data: inserted, error: insertErr } = await db
    .from("referrals")
    .insert({
      case_id: caseUuid,
      referred_by: user.sub,
      referring_facility_id: referringFacilityId,
      receiving_facility_id: receivingFacilityUuid,
      reason,
      urgency,
      sbar_version: SBAR_VERSION,
      sbar_draft: sbarDraft,
    })
    .select()
    .single();

  if (insertErr || !inserted) {
    console.warn("Failed to create referral:", insertErr);
    throw new HttpError(500, "Failed to create referral");
  }

  await logPhiAccess({
    eventType: AuditEventType.PHI_CREATE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "referrals",
    resourceId: inserted.id,
    facilityId: referringFacilityId,
    ipAddress: getClientIp(c),
    details: { case_id: caseUuid, receiving_facility_id: receivingFacilityUuid, urgency },
  });

  return c.json(inserted);
});

// ── List referrals ───────────────────────────────────────────────────────────

type Direction = "outgoing" | "incoming" | "all";

referral.get("/api/referrals", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const directionParam = c.req.query("direction") ?? "all";
  const direction: Direction = directionParam === "outgoing" || directionParam === "incoming" ? directionParam : "all";

  if (user.resolvedRole !== "admin" && !user.resolvedFacilityId) {
    return c.json({ referrals: [] });
  }

  const db = getSupabaseForUser(user.token);
  let query = db.from("referrals").select(REFERRAL_SELECT_COLUMNS).order("created_at", { ascending: false }).limit(
    200,
  );

  if (user.resolvedRole !== "admin") {
    const facilityId = user.resolvedFacilityId;
    if (direction === "outgoing") {
      query = query.eq("referring_facility_id", facilityId);
    } else if (direction === "incoming") {
      query = query.eq("receiving_facility_id", facilityId);
    } else {
      query = query.or(`referring_facility_id.eq.${facilityId},receiving_facility_id.eq.${facilityId}`);
    }
  }

  const { data, error } = await query;
  if (error) {
    console.warn("List referrals query failed:", error);
    throw new HttpError(502, "Referrals query failed — try again");
  }

  return c.json({ referrals: data ?? [] });
});

// ── Advance referral status ────────────────────────────────────────────────────

referral.patch(
  "/api/referrals/:referral_id/status",
  rateLimit(30, 60),
  requireRole("doctor", "admin"),
  async (c) => {
    const user = c.get("user");
    const referralUuid = parseUuid(c.req.param("referral_id")!, "referral_id");
    const body = await c.req.json().catch(() => ({}));
    const validStatuses = ["acknowledged", "patient_arrived", "completed", "cancelled"];
    if (!validStatuses.includes(body.status)) {
      throw new HttpError(400, "Invalid status");
    }

    const db = getSupabaseForUser(user.token);
    const { data: row, error: fetchErr } = await db
      .from("referrals")
      .select("id, case_id, receiving_facility_id, referring_facility_id, status")
      .eq("id", referralUuid)
      .maybeSingle();

    if (fetchErr || !row) {
      throw new HttpError(404, "Referral not found");
    }

    if (
      user.resolvedRole !== "admin" &&
      (!user.resolvedFacilityId || user.resolvedFacilityId !== row.receiving_facility_id)
    ) {
      throw new HttpError(403, "Only the receiving facility can update this referral");
    }

    const currentStatus = row.status;
    const allowed = ALLOWED_TRANSITIONS[currentStatus] ?? new Set();
    if (!allowed.has(body.status)) {
      throw new HttpError(409, `Cannot transition from ${currentStatus} to ${body.status}`);
    }

    const { data: updatedRows, error: updateErr } = await db
      .from("referrals")
      .update({
        status: body.status,
        updated_at: new Date().toISOString(),
      })
      .eq("id", referralUuid)
      .eq("status", currentStatus)
      .select();

    if (updateErr || !updatedRows || updatedRows.length === 0) {
      throw new HttpError(409, "Referral was modified concurrently. Please retry.");
    }

    // ADR §53: Automated post-discharge follow-up task generation
    // When receiving hospital doctor marks referral as completed, schedule
    // 48-hour follow-up task for the originating community worker.
    if (body.status === "completed" && row.case_id) {
      try {
        const { error: rpcErr } = await db.rpc("fn_mark_referral_followup_due", {
          p_case_id: row.case_id,
          p_referral_id: referralUuid,
        });
        if (rpcErr) {
          console.warn("Could not execute fn_mark_referral_followup_due RPC:", rpcErr);
        }
      } catch (e) {
        console.warn("Could not execute fn_mark_referral_followup_due RPC:", e);
      }
    }

    await logPhiAccess({
      eventType: AuditEventType.PHI_UPDATE,
      userId: user.sub ?? "unknown",
      userRole: user.resolvedRole,
      resourceType: "referrals",
      resourceId: referralUuid,
      facilityId: user.resolvedFacilityId,
      ipAddress: getClientIp(c),
      details: { status: body.status },
    });

    return c.json(updatedRows[0]);
  },
);
