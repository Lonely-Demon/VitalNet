// Ported from referral_routes.py — the two read-only endpoints
// (Tranche A). The write endpoints (facility capacity PATCH, create
// referral POST, advance-status PATCH) are Tranche B (Phase 4).
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { type Facility, mergeOpenCaseCounts, type OpenCaseCountRow } from "../_shared/facilities.ts";
import type { AppEnv } from "../_shared/types.ts";

export const referral = new Hono<AppEnv>();

const REFERRAL_SELECT_COLUMNS = "id, case_id, referred_by, referring_facility_id, receiving_facility_id, " +
  "reason, urgency, status, created_at, updated_at, " +
  "case_records(chief_complaint, patient_age, patient_sex, triage_level), " +
  "referring_facility:facilities!referring_facility_id(name), " +
  "receiving_facility:facilities!receiving_facility_id(name)";

// ── Facility picker (for the referral target dropdown) ─────────────────────

referral.get("/api/facilities", requireRole("doctor", "admin"), async (c) => {
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

  const merged = mergeOpenCaseCounts((facilities ?? []) as Facility[], (openCounts ?? []) as OpenCaseCountRow[]);
  return c.json(merged);
});

// ── List referrals ───────────────────────────────────────────────────────────

type Direction = "outgoing" | "incoming" | "all";

referral.get("/api/referrals", requireRole("doctor", "admin"), async (c) => {
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
