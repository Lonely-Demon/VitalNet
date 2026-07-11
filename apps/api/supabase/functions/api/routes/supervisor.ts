// Ported from supervisor_routes.py's GET /api/supervisor/team-metrics.
// Calls fn_team_metrics (phase28_security_definer_fns.sql, Phase 2)
// through the caller's own RLS-scoped client instead of supabase_admin.
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { resolveFacilityScope } from "../_shared/scoping.ts";
import { aggregateTeamMetrics, type TeamMetricsRow } from "../_shared/teamMetrics.ts";
import type { AppEnv } from "../_shared/types.ts";

export const supervisor = new Hono<AppEnv>();

const DEFAULT_WINDOW_DAYS = 30;
const MAX_WINDOW_DAYS = 366;

supervisor.get("/api/supervisor/team-metrics", rateLimit(60, 60), requireRole("supervisor", "admin"), async (c) => {
  const user = c.get("user");

  const daysParam = c.req.query("days");
  const days = daysParam ? Number.parseInt(daysParam, 10) : DEFAULT_WINDOW_DAYS;
  if (!Number.isFinite(days) || days < 1 || days > MAX_WINDOW_DAYS) {
    throw new HttpError(400, `days must be between 1 and ${MAX_WINDOW_DAYS}`);
  }

  const requestedFacilityId = c.req.query("facility_id") ?? null;
  const scopedFacilityId = resolveFacilityScope(user.resolvedRole, user.resolvedFacilityId, requestedFacilityId);

  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const db = getSupabaseForUser(user.token);
  const { data, error } = await db.rpc("fn_team_metrics", {
    p_facility_id: scopedFacilityId,
    p_since: since,
  });

  if (error) {
    console.warn("Supervisor team-metrics query failed:", error);
    throw new HttpError(502, "Team metrics query failed — try again");
  }

  const result = aggregateTeamMetrics((data ?? []) as TeamMetricsRow[]);

  return c.json({
    facility_id: scopedFacilityId,
    window_days: days,
    worker_count: result.length,
    workers: result,
  });
});
