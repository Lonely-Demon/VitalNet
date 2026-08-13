// Ported from outbreak_routes.py's GET /api/outbreak/signals. Calls
// fn_outbreak_signal_counts (phase28_security_definer_fns.sql, Phase 2)
// through the caller's own RLS-scoped client instead of supabase_admin
// -- the SQL function re-derives the same facility-scoping rule
// internally, so resolveFacilityScope here is only used to shape the
// response's echoed facility_id, not as the actual access boundary.
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { resolveFacilityScope } from "../_shared/scoping.ts";
import { BASELINE_DAYS, computeEarsSignals, type EarsRow } from "../_shared/ears.ts";
import type { AppEnv } from "../_shared/types.ts";

export const outbreak = new Hono<AppEnv>();

outbreak.get("/api/outbreak/signals", rateLimit(60, 60), requireRole("doctor", "supervisor", "admin"), async (c) => {
  const user = c.get("user");
  const requestedFacilityId = c.req.query("facility_id") ?? null;
  const scopedFacilityId = resolveFacilityScope(user.resolvedRole, user.resolvedFacilityId, requestedFacilityId);

  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  const since = new Date(now.getTime() - (BASELINE_DAYS + 1) * 24 * 60 * 60 * 1000).toISOString();

  const db = getSupabaseForUser(user.token);
  const { data, error } = await db.rpc("fn_outbreak_signal_counts", {
    p_facility_id: scopedFacilityId,
    p_since: since,
  });

  if (error) {
    console.warn("Outbreak signals query failed:", error);
    throw new HttpError(502, "Outbreak signals query failed — try again");
  }

  const signals = computeEarsSignals((data ?? []) as EarsRow[], today);

  return c.json({
    facility_id: scopedFacilityId,
    date: today,
    baseline_days: BASELINE_DAYS,
    signal_count: signals.length,
    signals,
  });
});
