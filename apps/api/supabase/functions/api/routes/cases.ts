// Ported from app/api/routes/cases.py — the full case surface, INCLUDING
// the Round 6 rebuild plan's centerpiece: POST /api/submit now computes
// triage_level via @vitalnet/clinical-core's triage() in "rules_first"
// mode instead of the Python backend's ML-authoritative predict_triage().
// The rules engine (packages/clinical-core/src/rules/engine.ts) is the
// SOLE source of triage_level; the advisory tree model (bundled via
// _shared/model.ts) only ever contributes model_tier/model_agreed —
// see triage.ts's module header for the full design rationale.
import { Hono } from "hono";
import { z } from "zod";
// @deno-types="../../../../../../packages/clinical-core/dist/index.d.ts"
import { intakeFormSchema, PATIENT_KEY_RE, stripControlChars, triage } from "@vitalnet/clinical-core";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { extractBearerToken, getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { AuditEventType, getClientIp, logPhiAccess } from "../_shared/audit.ts";
import {
  authorizeCaseRowAccess,
  type CaseRowAuth,
  fetchAuthorizedCase,
  formatRiskDriver,
  normalizedIsoTs,
  parseUuid,
  sanitizeMedicalText,
} from "../_shared/cases.ts";
import { generateBriefing, generatePatientSummary } from "../_shared/llm.ts";
import { pushEmergencyAlert } from "../_shared/webpush.ts";
import { FEATURE_NAMES, TRIAGE_TREES } from "../_shared/model.ts";
import type { AppEnv } from "../_shared/types.ts";

export const cases = new Hono<AppEnv>();

// supabase-js infers .select(...) column types from a literal select
// string; a concatenated one (below, for readability) loses that
// inference, so the list-query result rows are cast through these minimal
// shapes instead — same pattern as _shared/analyticsStats.ts's AshaWorkerRow.
interface CaseListRow {
  id: string;
  created_at: string;
  triage_priority: number;
  [key: string]: unknown;
}

interface MyCaseRow {
  id: string;
  created_at: string;
  [key: string]: unknown;
}

// Identifies which DECISION SYSTEM produced triage_level, not a model
// checkpoint — the column predates the rules-first flip, when it tracked
// the ML classifier's pickle version. The advisory model's own version (if
// one ran) is separately visible via model_tier being non-null plus
// features_config.json's model_version.
const TRIAGE_MODEL_VERSION = "clinical-core/rules_first";

/** Fire a promise without blocking the response. Uses Supabase Edge
 * Runtime's waitUntil() when available (keeps the isolate alive until the
 * promise settles, the Deno-native equivalent of FastAPI's BackgroundTasks)
 * and falls back to a bare unawaited call for local `deno run`/tests. */
function runInBackground(promise: Promise<unknown>): void {
  const rt = (globalThis as { EdgeRuntime?: { waitUntil: (p: Promise<unknown>) => void } }).EdgeRuntime;
  const guarded = promise.catch((e) => console.warn("Background task failed:", e));
  if (rt) {
    rt.waitUntil(guarded);
  }
}

const triageOverrideSchema = z.object({
  overridden_triage: z.enum(["ROUTINE", "URGENT", "EMERGENCY"]),
  override_reason: z.string().min(1).max(500).transform(stripControlChars),
});

const caseOutcomeSchema = z.object({
  actual_severity: z.enum(["ROUTINE", "URGENT", "EMERGENCY"]),
  patient_disposition: z.enum([
    "treated_discharged",
    "admitted",
    "referred_higher_facility",
    "deceased",
    "unknown",
  ]),
  outcome_notes: z.string().max(1000).transform(stripControlChars).optional(),
});

async function readJsonBody(c: { req: { json: () => Promise<unknown> } }): Promise<unknown> {
  try {
    return await c.req.json();
  } catch {
    throw new HttpError(400, "Invalid JSON body");
  }
}

// Cross-visit deterioration pattern: a repeated URGENT/EMERGENCY
// presentation from the same patient within this trailing window is a
// signal worth a clinician's eyes even if today's reading alone wouldn't
// trigger review.
const DETERIORATION_WINDOW_DAYS = 7;

async function checkDeteriorationPattern(
  db: ReturnType<typeof getSupabaseForUser>,
  patientKey: string | null | undefined,
  currentTriageLevel: string,
): Promise<{ alert: boolean; visitCount: number | null }> {
  if (!patientKey) return { alert: false, visitCount: null };

  const { data, error } = await db.rpc("fn_deterioration_count", {
    p_patient_key: patientKey,
    p_current_triage_level: currentTriageLevel,
    p_window_days: DETERIORATION_WINDOW_DAYS,
  });
  if (error) throw error;
  const row = (data ?? [{}])[0] ?? {};
  return { alert: Boolean(row.has_pattern), visitCount: row.visit_count ?? null };
}

// ── Submit Case ────────────────────────────────────────────────────────────

cases.post("/api/submit", rateLimit(20, 60), requireRole("asha_worker", "admin"), async (c) => {
  const user = c.get("user");
  const rawBody = await readJsonBody(c);
  const parsed = intakeFormSchema.safeParse(rawBody);
  if (!parsed.success) {
    const errors: Record<string, string> = {};
    for (const issue of parsed.error.issues) errors[issue.path.join(".")] = issue.message;
    throw new HttpError(400, JSON.stringify({ detail: "Validation failed", errors }));
  }
  const form = parsed.data;

  const role = user.resolvedRole;
  const facilityId = user.resolvedFacilityId;
  if (role === "asha_worker" && !facilityId) {
    throw new HttpError(403, "User is not assigned to a facility");
  }

  try {
    const patientName = sanitizeMedicalText(form.patient_name, 500) ?? form.patient_name;
    const chiefComplaint = sanitizeMedicalText(form.chief_complaint, 200) ?? form.chief_complaint;
    const location = sanitizeMedicalText(form.location, 500) ?? form.location;
    const observations = form.observations !== undefined
      ? sanitizeMedicalText(form.observations, 500) ?? form.observations
      : form.observations;
    const knownConditions = form.known_conditions !== undefined
      ? sanitizeMedicalText(form.known_conditions, 500) ?? form.known_conditions
      : form.known_conditions;
    const currentMedications = form.current_medications !== undefined
      ? sanitizeMedicalText(form.current_medications, 500) ?? form.current_medications
      : form.current_medications;

    // Step 1: rules-first triage (always runs — LLM-independent, network-independent).
    const result = triage(
      {
        patient_age: form.patient_age,
        patient_sex: form.patient_sex,
        bp_systolic: form.bp_systolic ?? null,
        bp_diastolic: form.bp_diastolic ?? null,
        spo2: form.spo2 ?? null,
        heart_rate: form.heart_rate ?? null,
        temperature: form.temperature ?? null,
        symptoms: form.symptoms,
        is_pregnant: form.is_pregnant ?? null,
        chief_complaint: chiefComplaint,
        complaint_duration: form.complaint_duration,
        location,
        known_conditions: knownConditions ?? null,
        current_medications: currentMedications ?? null,
      },
      { mode: "rules_first", trees: TRIAGE_TREES, featureNames: FEATURE_NAMES },
    );

    const riskDriver = formatRiskDriver(result.tier, result.firedRules);
    const triageConfidence = result.model?.confidence ?? 1.0;
    const lowConfidence = result.model?.lowConfidence ?? false;

    const briefing = await generateBriefing(
      {
        patient_age: form.patient_age,
        patient_sex: form.patient_sex,
        location,
        chief_complaint: chiefComplaint,
        complaint_duration: form.complaint_duration,
        bp_systolic: form.bp_systolic,
        bp_diastolic: form.bp_diastolic,
        spo2: form.spo2,
        heart_rate: form.heart_rate,
        temperature: form.temperature,
        symptoms: form.symptoms,
        observations,
        known_conditions: knownConditions,
        current_medications: currentMedications,
      },
      {
        triage_level: result.tier,
        confidence_score: triageConfidence,
        risk_driver: riskDriver,
        low_confidence: lowConfidence,
      },
    );

    const rawToken = extractBearerToken(c.req.header("authorization"));
    const db = getSupabaseForUser(rawToken);

    const { alert: deteriorationAlert, visitCount: deteriorationVisitCount } = await checkDeteriorationPattern(
      db,
      form.patient_key,
      result.tier,
    );

    const record = {
      client_id: form.client_id ?? crypto.randomUUID(),
      submitted_by: user.sub,
      facility_id: facilityId,
      patient_name: patientName,
      patient_age: form.patient_age,
      patient_sex: form.patient_sex,
      patient_location: location,
      bp_systolic: form.bp_systolic ?? null,
      bp_diastolic: form.bp_diastolic ?? null,
      spo2: form.spo2 ?? null,
      heart_rate: form.heart_rate ?? null,
      temperature: form.temperature ?? null,
      is_pregnant: form.is_pregnant ?? null,
      chief_complaint: chiefComplaint,
      complaint_duration: form.complaint_duration,
      symptoms: form.symptoms ?? [],
      observations: observations ?? null,
      known_conditions: knownConditions ?? null,
      current_medications: currentMedications ?? null,
      human_review_requested: form.human_review_requested,
      human_review_reason: form.human_review_reason ?? null,
      patient_key: form.patient_key ?? null,
      consent_captured: form.consent_captured,
      consent_captured_at: form.consent_captured_at ?? new Date().toISOString(),
      triage_level: result.tier,
      triage_confidence: triageConfidence,
      risk_driver: riskDriver,
      triage_model_version: TRIAGE_MODEL_VERSION,
      low_confidence: lowConfidence,
      contraindication_flags: result.contraindicationFlags ?? [],
      deterioration_alert: deteriorationAlert,
      deterioration_visit_count: deteriorationVisitCount,
      llm_status: briefing.llm_status ?? "generated",
      needs_review: Boolean(
        briefing.needs_review ||
          form.human_review_requested ||
          (result.contraindicationFlags && result.contraindicationFlags.length > 0) ||
          deteriorationAlert,
      ),
      briefing,
      llm_model_used: briefing._model_used ?? "unknown",
      created_offline: form.created_offline,
      client_submitted_at: form.client_submitted_at ?? null,
      // Advisory ML output (phase29_events_and_advisory_model.sql) —
      // additive, never influences triage_level above.
      model_tier: result.model?.tier ?? null,
      rules_fired: result.firedRules ?? [],
      model_agreed: result.modelAgreed ?? null,
    };

    const { data: upserted, error: upsertError } = await db
      .from("case_records")
      .upsert(record, { onConflict: "client_id", ignoreDuplicates: true })
      .select();
    if (upsertError) throw upsertError;

    const isNewSubmission = Boolean(upserted && upserted.length > 0);
    let response: Record<string, unknown>;
    if (!isNewSubmission) {
      // Upsert ignored the duplicate; fetch the existing row to return to the client.
      const { data: existing, error: existingError } = await db
        .from("case_records")
        .select("id, client_id, triage_level, triage_confidence, risk_driver, created_at, created_offline, facility_id")
        .eq("client_id", record.client_id);
      if (existingError) throw existingError;
      response = (existing && existing[0]) || record;
    } else {
      response = upserted![0]!;
    }

    await logPhiAccess({
      eventType: AuditEventType.PHI_CREATE,
      userId: user.sub ?? "unknown",
      userRole: role,
      resourceType: "case_records",
      resourceId: typeof response.id === "string" ? response.id : null,
      facilityId,
      ipAddress: getClientIp(c),
      details: { created_offline: Boolean(form.created_offline), needs_review: Boolean(record.needs_review) },
    });

    // Genuinely new EMERGENCY case (not a retried duplicate) — notify the
    // facility's subscribed doctors. Backgrounded: never adds latency to
    // the ASHA worker's submission response; pushEmergencyAlert() itself
    // no-ops safely if VAPID isn't configured.
    if (isNewSubmission && result.tier === "EMERGENCY") {
      runInBackground(
        pushEmergencyAlert(facilityId, "EMERGENCY case submitted", `${chiefComplaint} — ${riskDriver}`.slice(0, 150)),
      );
    }

    return c.json(response);
  } catch (e) {
    if (e instanceof HttpError) throw e;
    console.error(`submit_case failed for client_id=${form.client_id ?? "(none)"}:`, e);
    throw new HttpError(500, "An internal server error occurred. The case was not saved. Please retry.");
  }
});

// ── Get Cases ──────────────────────────────────────────────────────────────

cases.get("/api/cases", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);
  const role = user.resolvedRole;
  const facilityId = user.resolvedFacilityId;

  const limitParam = Number.parseInt(c.req.query("limit") ?? "25", 10);
  const limit = Math.max(1, Math.min(Number.isFinite(limitParam) ? limitParam : 25, 100));

  const beforeTimeRaw = c.req.query("before_time");
  const beforePriorityRaw = c.req.query("before_priority");
  const beforeIdRaw = c.req.query("before_id");

  let beforePriority: number | null = null;
  if (beforePriorityRaw !== undefined) {
    beforePriority = Number.parseInt(beforePriorityRaw, 10);
    if (![0, 1, 2].includes(beforePriority)) {
      throw new HttpError(400, "Invalid before_priority");
    }
  }

  const normalizedBeforeTime = beforeTimeRaw ? normalizedIsoTs(beforeTimeRaw, "before_time") : null;
  const parsedBeforeId = beforeIdRaw ? parseUuid(beforeIdRaw, "before_id") : null;

  let query = db
    .from("case_records")
    .select(
      "id, patient_name, patient_age, patient_sex, patient_location, chief_complaint, " +
        "triage_level, triage_priority, triage_confidence, risk_driver, briefing, " +
        "low_confidence, needs_review, human_review_requested, human_review_reason, " +
        "contraindication_flags, deterioration_alert, deterioration_visit_count, " +
        "triage_model_version, overridden_triage, override_reason, overridden_by, overridden_at, " +
        "created_at, reviewed_at, reviewed_by, facility_id, created_offline",
    )
    .is("deleted_at", null)
    .order("triage_priority", { ascending: true })
    .order("created_at", { ascending: false })
    .order("id", { ascending: false })
    .limit(limit + 1);

  if (role === "doctor" && facilityId) {
    query = query.eq("facility_id", facilityId);
  }

  if (normalizedBeforeTime !== null && beforePriority !== null) {
    query = parsedBeforeId !== null
      ? query.or(
        `triage_priority.gt.${beforePriority},` +
          `and(triage_priority.eq.${beforePriority},created_at.lt.${normalizedBeforeTime}),` +
          `and(triage_priority.eq.${beforePriority},created_at.eq.${normalizedBeforeTime},id.lt.${parsedBeforeId})`,
      )
      : query.or(
        `triage_priority.gt.${beforePriority},` +
          `and(triage_priority.eq.${beforePriority},created_at.lt.${normalizedBeforeTime})`,
      );
  }

  const { data, error } = await query;
  if (error) {
    console.warn("List cases query failed:", error);
    throw new HttpError(502, "Cases query failed — try again");
  }

  const rows = (data ?? []) as unknown as CaseListRow[];
  const hasMore = rows.length > limit;
  const page = rows.slice(0, limit);
  const last = page[page.length - 1];

  return c.json({
    cases: page,
    hasMore,
    nextCursor: hasMore && last ? last.created_at : null,
    nextTriagePriority: hasMore && last ? last.triage_priority : null,
    nextId: hasMore && last ? last.id : null,
  });
});

// ── ASHA: My Submissions ───────────────────────────────────────────────────
// Registered before /api/cases/:case_id (below) — "mine" would otherwise be
// swallowed as a literal case_id value, matching cases.py's own source order.

cases.get("/api/cases/mine", rateLimit(60, 60), requireRole("asha_worker", "admin"), async (c) => {
  const user = c.get("user");
  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);

  const limitParam = Number.parseInt(c.req.query("limit") ?? "25", 10);
  const limit = Math.max(1, Math.min(Number.isFinite(limitParam) ? limitParam : 25, 100));
  const beforeRaw = c.req.query("before");
  const beforeIdRaw = c.req.query("before_id");

  const normalizedBefore = beforeRaw ? normalizedIsoTs(beforeRaw, "before") : null;
  const parsedBeforeId = beforeIdRaw ? parseUuid(beforeIdRaw, "before_id") : null;

  let query = db
    .from("case_records")
    .select("id, patient_name, chief_complaint, triage_level, created_at, reviewed_at, patient_age, patient_sex")
    .eq("submitted_by", user.sub)
    .is("deleted_at", null)
    .order("created_at", { ascending: false })
    .order("id", { ascending: false })
    .limit(limit + 1);

  if (normalizedBefore && parsedBeforeId) {
    query = query.or(
      `created_at.lt.${normalizedBefore},and(created_at.eq.${normalizedBefore},id.lt.${parsedBeforeId})`,
    );
  } else if (normalizedBefore) {
    query = query.lt("created_at", normalizedBefore);
  }

  const { data, error } = await query;
  if (error) {
    console.warn("My-cases query failed:", error);
    throw new HttpError(502, "Cases query failed — try again");
  }

  const rows = (data ?? []) as unknown as MyCaseRow[];
  const hasMore = rows.length > limit;
  const page = rows.slice(0, limit);
  const last = page[page.length - 1];

  return c.json({
    cases: page,
    hasMore,
    nextCursor: hasMore && last ? last.created_at : null,
    nextId: hasMore && last ? last.id : null,
  });
});

// ── Get Case History By Patient Key ───────────────────────────────────────
// Also registered before /api/cases/:case_id, for the same reason as /mine.

cases.get(
  "/api/cases/by-patient-key/:patient_key",
  rateLimit(60, 60),
  requireRole("asha_worker", "doctor", "admin"),
  async (c) => {
    const user = c.get("user");
    const key = (c.req.param("patient_key") || "").trim().toUpperCase();
    if (!PATIENT_KEY_RE.test(key)) {
      throw new HttpError(400, "Invalid patient_key format");
    }

    const rawToken = extractBearerToken(c.req.header("authorization"));
    const db = getSupabaseForUser(rawToken);
    const role = user.resolvedRole;
    const facilityId = user.resolvedFacilityId;

    let query = db
      .from("case_records")
      .select("id, chief_complaint, triage_level, created_at, reviewed_at, patient_age, patient_sex, facility_id")
      .eq("patient_key", key)
      .is("deleted_at", null)
      .order("created_at", { ascending: false })
      .limit(50);

    if (role === "doctor" && facilityId) {
      query = query.eq("facility_id", facilityId);
    }

    const { data, error } = await query;
    if (error) {
      console.warn("by-patient-key query failed:", error);
      throw new HttpError(502, "Cases query failed — try again");
    }
    const rows = data ?? [];

    await logPhiAccess({
      eventType: AuditEventType.PHI_READ,
      userId: user.sub ?? "unknown",
      userRole: role,
      resourceType: "case_records",
      resourceId: null,
      facilityId,
      ipAddress: getClientIp(c),
      details: { view: "patient_key_history", match_count: rows.length },
    });

    return c.json({ cases: rows });
  },
);

// ── Review Case ────────────────────────────────────────────────────────────

cases.patch("/api/cases/:case_id/review", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);
  const role = user.resolvedRole;

  const caseRow = await fetchAuthorizedCase(db, caseUuid, user);

  const { data: updated, error: updateError } = await db
    .from("case_records")
    .update({ reviewed_by: user.sub, reviewed_at: new Date().toISOString() })
    .eq("id", caseUuid)
    .is("deleted_at", null)
    .select();
  if (updateError) throw updateError;
  if (!updated || updated.length === 0) {
    throw new HttpError(409, "Case could not be reviewed or already deleted");
  }

  const { error: reviewInsertError } = await db.from("case_reviews").insert({
    case_id: caseUuid,
    reviewer_id: user.sub,
    note: "Marked reviewed via API",
  });
  if (reviewInsertError) throw reviewInsertError;

  await logPhiAccess({
    eventType: AuditEventType.PHI_UPDATE,
    userId: user.sub ?? "unknown",
    userRole: role,
    resourceType: "case_records",
    resourceId: caseUuid,
    facilityId: caseRow.facility_id,
    ipAddress: getClientIp(c),
    details: { action: "review" },
  });

  return c.json({ status: "reviewed", case_id: caseUuid, reviewed_by: user.sub });
});

// ── Triage Override ──────────────────────────────────────────────────────

cases.patch("/api/cases/:case_id/triage-override", rateLimit(30, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
  const rawBody = await readJsonBody(c);
  const parsed = triageOverrideSchema.safeParse(rawBody);
  if (!parsed.success) {
    throw new HttpError(400, parsed.error.issues.map((i) => i.message).join("; "));
  }
  const body = parsed.data;

  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);
  const role = user.resolvedRole;

  const caseRow = await fetchAuthorizedCase(db, caseUuid, user);

  const { data: updated, error } = await db
    .from("case_records")
    .update({
      overridden_triage: body.overridden_triage,
      override_reason: body.override_reason,
      overridden_by: user.sub,
      overridden_at: new Date().toISOString(),
    })
    .eq("id", caseUuid)
    .is("deleted_at", null)
    .select();
  if (error) throw error;
  if (!updated || updated.length === 0) {
    throw new HttpError(409, "Case could not be updated or already deleted");
  }

  await logPhiAccess({
    eventType: AuditEventType.PHI_UPDATE,
    userId: user.sub ?? "unknown",
    userRole: role,
    resourceType: "case_records",
    resourceId: caseUuid,
    facilityId: caseRow.facility_id,
    ipAddress: getClientIp(c),
    details: { action: "triage_override", overridden_triage: body.overridden_triage },
  });

  return c.json({
    status: "overridden",
    case_id: caseUuid,
    overridden_triage: body.overridden_triage,
    overridden_by: user.sub,
  });
});

// ── Case Outcome ───────────────────────────────────────────────────────────

cases.patch("/api/cases/:case_id/outcome", rateLimit(30, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
  const rawBody = await readJsonBody(c);
  const parsed = caseOutcomeSchema.safeParse(rawBody);
  if (!parsed.success) {
    throw new HttpError(400, parsed.error.issues.map((i) => i.message).join("; "));
  }
  const body = parsed.data;

  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);
  const role = user.resolvedRole;

  const caseRow = await fetchAuthorizedCase(db, caseUuid, user);

  const { data: inserted, error } = await db
    .from("case_outcomes")
    .insert({
      case_id: caseUuid,
      recorded_by: user.sub,
      actual_severity: body.actual_severity,
      patient_disposition: body.patient_disposition,
      outcome_notes: body.outcome_notes ?? null,
    })
    .select();
  if (error) throw error;
  if (!inserted || inserted.length === 0) {
    throw new HttpError(500, "Failed to record outcome");
  }

  await logPhiAccess({
    eventType: AuditEventType.PHI_CREATE,
    userId: user.sub ?? "unknown",
    userRole: role,
    resourceType: "case_outcomes",
    resourceId: caseUuid,
    facilityId: caseRow.facility_id,
    ipAddress: getClientIp(c),
    details: { actual_severity: body.actual_severity, patient_disposition: body.patient_disposition },
  });

  return c.json(inserted[0]);
});

// ── Get Case Detail ────────────────────────────────────────────────────────

cases.get("/api/cases/:case_id", rateLimit(60, 60), requireRole("asha_worker", "doctor", "admin"), async (c) => {
  const user = c.get("user");
  const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);

  const { data, error } = await db
    .from("case_records")
    .select("*")
    .eq("id", caseUuid)
    .is("deleted_at", null)
    .maybeSingle();
  if (error) throw error;
  if (!data) throw new HttpError(404, "Case not found");

  authorizeCaseRowAccess(user, data as CaseRowAuth);

  await logPhiAccess({
    eventType: AuditEventType.PHI_READ,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "case_records",
    resourceId: caseUuid,
    facilityId: (data as CaseRowAuth).facility_id,
    ipAddress: getClientIp(c),
    details: { view: "detail" },
  });

  return c.json(data);
});

cases.post(
  "/api/cases/:case_id/patient-summary",
  rateLimit(20, 60),
  requireRole("asha_worker", "doctor", "admin"),
  async (c) => {
    const user = c.get("user");
    const caseUuid = parseUuid(c.req.param("case_id")!, "case_id");
    const language = c.req.query("language") ?? "en";
    const rawToken = extractBearerToken(c.req.header("authorization"));
    const db = getSupabaseForUser(rawToken);

    const { data, error } = await db
      .from("case_records")
      .select("id, facility_id, submitted_by, triage_level, risk_driver, briefing, deleted_at")
      .eq("id", caseUuid)
      .maybeSingle();
    if (error) throw error;
    if (!data || data.deleted_at !== null) throw new HttpError(404, "Case not found");

    authorizeCaseRowAccess(user, data as CaseRowAuth);

    const triageResult = { triage_level: String(data.triage_level), risk_driver: String(data.risk_driver ?? "") };
    const briefing = (data.briefing as Record<string, unknown>) ?? {};
    const summary = await generatePatientSummary(briefing, triageResult, language);

    return c.json(summary);
  },
);
