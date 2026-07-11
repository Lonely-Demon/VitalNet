// Ported from analytics_routes.py — all five endpoints (GET /summary,
// /emergency-rate, /response-times, /ml-agreement, /export). Every query
// uses the caller's own RLS-scoped client (analytics_routes.py never
// imported supabase_admin — 'doctor'/'admin' can already see their own
// facility's case_records under RLS, unlike asha_worker), so no new
// SECURITY DEFINER function was needed. Queries in /summary run
// concurrently with a per-query timeout and graceful degradation (partial
// data + a `_degraded` flag), matching the Python original's
// asyncio.gather + _run_query pattern via runQuery()/Promise.allSettled.
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { runQuery } from "../_shared/queryTimeout.ts";
import { AuditEventType, getClientIp, logPhiAccess } from "../_shared/audit.ts";
import { toCsv } from "../_shared/csv.ts";
import {
  type AshaWorkerRow,
  buildDailyVolume,
  buildEmergencyRateByWeek,
  buildMlAgreement,
  buildResponseTimes,
  buildTriageDistribution,
  type MlAgreementRow,
  type ResponseTimesRow,
  topAshaWorkers,
} from "../_shared/analyticsStats.ts";
import type { AppEnv } from "../_shared/types.ts";

export const analytics = new Hono<AppEnv>();

const GLOBAL_SCOPE_ROLE = "admin";

function resolveScope(user: { resolvedRole: string; resolvedFacilityId: string | null }) {
  const scoped = user.resolvedRole !== GLOBAL_SCOPE_ROLE && Boolean(user.resolvedFacilityId);
  return { role: user.resolvedRole, facilityId: user.resolvedFacilityId, scoped };
}

// ── /summary ──────────────────────────────────────────────────────────────────

analytics.get("/api/analytics/summary", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const db = getSupabaseForUser(user.token);
  const { facilityId, scoped } = resolveScope(user);

  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const monthSince = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

  const failures: string[] = [];
  const [totalRes, distRes, weekRes, reviewedRes, ashaRes] = await Promise.all([
    runQuery(
      async () => {
        let q = db.from("case_records").select("id", { count: "exact" }).is("deleted_at", null);
        if (scoped) q = q.eq("facility_id", facilityId);
        // supabase-js returns PostgREST errors as { data: null, error }
        // WITHOUT throwing (unlike supabase-py, which raises) — throw
        // explicitly so runQuery records the failure and the endpoint
        // degrades with a _degraded flag instead of silently serving
        // zeros as if they were real data.
        const res = await q;
        if (res.error) throw res.error;
        return res;
      },
      "total",
      failures,
    ),
    runQuery(
      async () => {
        let q = db.from("case_records").select("triage_level").is("deleted_at", null);
        if (scoped) q = q.eq("facility_id", facilityId);
        // supabase-js returns PostgREST errors as { data: null, error }
        // WITHOUT throwing (unlike supabase-py, which raises) — throw
        // explicitly so runQuery records the failure and the endpoint
        // degrades with a _degraded flag instead of silently serving
        // zeros as if they were real data.
        const res = await q;
        if (res.error) throw res.error;
        return res;
      },
      "triage_dist",
      failures,
    ),
    runQuery(
      async () => {
        let q = db.from("case_records").select("created_at").is("deleted_at", null).gte("created_at", since);
        if (scoped) q = q.eq("facility_id", facilityId);
        // supabase-js returns PostgREST errors as { data: null, error }
        // WITHOUT throwing (unlike supabase-py, which raises) — throw
        // explicitly so runQuery records the failure and the endpoint
        // degrades with a _degraded flag instead of silently serving
        // zeros as if they were real data.
        const res = await q;
        if (res.error) throw res.error;
        return res;
      },
      "week_cases",
      failures,
    ),
    runQuery(
      async () => {
        let q = db.from("case_records").select("id", { count: "exact" }).is("deleted_at", null).not(
          "reviewed_at",
          "is",
          null,
        );
        if (scoped) q = q.eq("facility_id", facilityId);
        // supabase-js returns PostgREST errors as { data: null, error }
        // WITHOUT throwing (unlike supabase-py, which raises) — throw
        // explicitly so runQuery records the failure and the endpoint
        // degrades with a _degraded flag instead of silently serving
        // zeros as if they were real data.
        const res = await q;
        if (res.error) throw res.error;
        return res;
      },
      "reviewed",
      failures,
    ),
    runQuery(
      async () => {
        let q = db.from("case_records").select("submitted_by, profiles!submitted_by(full_name)").is(
          "deleted_at",
          null,
        ).gte("created_at", monthSince);
        if (scoped) q = q.eq("facility_id", facilityId);
        // supabase-js returns PostgREST errors as { data: null, error }
        // WITHOUT throwing (unlike supabase-py, which raises) — throw
        // explicitly so runQuery records the failure and the endpoint
        // degrades with a _degraded flag instead of silently serving
        // zeros as if they were real data.
        const res = await q;
        if (res.error) throw res.error;
        return res;
      },
      "asha_workers",
      failures,
    ),
  ]);

  const total = totalRes?.count ?? 0;
  const dist = buildTriageDistribution((distRes?.data ?? []) as Array<{ triage_level: string | null }>);
  const daily = buildDailyVolume((weekRes?.data ?? []) as Array<{ created_at: string }>);
  const reviewed = reviewedRes?.count ?? 0;
  // Cast through unknown: without an explicit Database schema, supabase-js
  // guesses `profiles` is an array for this embed; PostgREST's actual
  // runtime response for a to-one FK embed (submitted_by -> profiles.id)
  // is a single object, matching AshaWorkerRow.
  const topAsha = topAshaWorkers((ashaRes?.data ?? []) as unknown as AshaWorkerRow[]);

  const response: Record<string, unknown> = {
    total_cases: total,
    triage_distribution: dist,
    daily_volume: daily,
    reviewed_count: reviewed,
    unreviewed_count: total - reviewed,
    top_asha_workers: topAsha,
  };
  if (failures.length) {
    response._degraded = true;
    response._failed_queries = failures;
  }
  return c.json(response);
});

// ── /emergency-rate ───────────────────────────────────────────────────────────

analytics.get("/api/analytics/emergency-rate", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const db = getSupabaseForUser(user.token);
  const { facilityId, scoped } = resolveScope(user);

  const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

  const failures: string[] = [];
  const res = await runQuery(
    async () => {
      let q = db.from("case_records").select("triage_level, created_at").is("deleted_at", null).gte(
        "created_at",
        since,
      );
      if (scoped) q = q.eq("facility_id", facilityId);
      // Same as /summary: supabase-js does NOT throw on PostgREST errors.
      const res = await q;
      if (res.error) throw res.error;
      return res;
    },
    "emergency_rate",
    failures,
  );

  const rows = (res?.data ?? []) as Array<{ triage_level: string | null; created_at: string }>;
  const weeks = buildEmergencyRateByWeek(rows);

  const response: Record<string, unknown> = { weeks };
  if (failures.length) response._degraded = true;
  return c.json(response);
});

// ── /response-times ───────────────────────────────────────────────────────────

analytics.get("/api/analytics/response-times", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const db = getSupabaseForUser(user.token);
  const { facilityId, scoped } = resolveScope(user);

  const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

  const failures: string[] = [];
  const res = await runQuery(
    async () => {
      let q = db.from("case_records").select("triage_level, created_at, reviewed_at").is("deleted_at", null).gte(
        "created_at",
        since,
      );
      if (scoped) q = q.eq("facility_id", facilityId);
      // Same as /summary: supabase-js does NOT throw on PostgREST errors.
      const res = await q;
      if (res.error) throw res.error;
      return res;
    },
    "response_times",
    failures,
  );

  const rows = (res?.data ?? []) as ResponseTimesRow[];
  const tiers = buildResponseTimes(rows, new Date());

  const response: Record<string, unknown> = { tiers };
  if (failures.length) response._degraded = true;
  return c.json(response);
});

// ── /ml-agreement ─────────────────────────────────────────────────────────────

analytics.get("/api/analytics/ml-agreement", rateLimit(60, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const db = getSupabaseForUser(user.token);
  const { facilityId, scoped } = resolveScope(user);

  const failures: string[] = [];
  const res = await runQuery(
    async () => {
      // model_tier, not triage_level — see analyticsStats.ts's buildMlAgreement
      // header for why this endpoint grades the advisory model's opinion, not
      // the (now rules-authoritative) triage decision.
      let q = db.from("case_outcomes").select("actual_severity, case_records!inner(model_tier, facility_id)");
      if (scoped) q = q.eq("case_records.facility_id", facilityId);
      // Same as /summary: supabase-js does NOT throw on PostgREST errors.
      const res = await q;
      if (res.error) throw res.error;
      return res;
    },
    "ml_agreement",
    failures,
  );

  const rows = (res?.data ?? []) as unknown as MlAgreementRow[];
  const result = buildMlAgreement(rows);

  const response: Record<string, unknown> = { ...result };
  if (failures.length) response._degraded = true;
  return c.json(response);
});

// ── /export ────────────────────────────────────────────────────────────────────

const EXPORT_MAX_RANGE_DAYS = 366;
const EXPORT_COLUMNS = [
  "id",
  "created_at",
  "reviewed_at",
  "triage_level",
  "triage_confidence",
  "overridden_triage",
  "override_reason",
  "risk_driver",
  "chief_complaint",
  "patient_age",
  "patient_sex",
  "patient_location",
  "facility_id",
  "submitted_by",
  "reviewed_by",
  "needs_review",
  "triage_model_version",
];

analytics.get("/api/analytics/export", rateLimit(10, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const dateFrom = c.req.query("date_from");
  const dateTo = c.req.query("date_to");
  if (!dateFrom || !dateTo) {
    throw new HttpError(400, "date_from and date_to are required");
  }

  const parsedFrom = new Date(dateFrom);
  const parsedTo = new Date(dateTo);
  if (Number.isNaN(parsedFrom.getTime()) || Number.isNaN(parsedTo.getTime())) {
    throw new HttpError(400, "date_from/date_to must be ISO 8601 dates");
  }
  if (parsedTo < parsedFrom) {
    throw new HttpError(400, "date_to must be after date_from");
  }
  if ((parsedTo.getTime() - parsedFrom.getTime()) / 86_400_000 > EXPORT_MAX_RANGE_DAYS) {
    throw new HttpError(400, `Date range cannot exceed ${EXPORT_MAX_RANGE_DAYS} days`);
  }

  const db = getSupabaseForUser(user.token);
  const { role, facilityId, scoped } = resolveScope(user);

  const failures: string[] = [];
  const res = await runQuery(
    async () => {
      let q = db.from("case_records").select(EXPORT_COLUMNS.join(",")).is("deleted_at", null).gte(
        "created_at",
        parsedFrom.toISOString(),
      ).lte("created_at", parsedTo.toISOString()).order("created_at", { ascending: true });
      if (scoped) q = q.eq("facility_id", facilityId);
      // Same as /summary: supabase-js does NOT throw on PostgREST errors.
      const res = await q;
      if (res.error) throw res.error;
      return res;
    },
    "export",
    failures,
  );

  if (failures.length) {
    throw new HttpError(502, "Export query failed — try a narrower date range");
  }
  const rows = (res?.data ?? []) as unknown as Array<Record<string, unknown>>;

  const csv = toCsv(EXPORT_COLUMNS, rows);

  await logPhiAccess({
    eventType: AuditEventType.PHI_EXPORT,
    userId: (user.sub as string | undefined) ?? "unknown",
    userRole: role,
    resourceType: "case_records",
    resourceId: null,
    facilityId: scoped ? facilityId : null,
    ipAddress: getClientIp(c),
    details: { row_count: rows.length, date_from: dateFrom, date_to: dateTo },
  });

  // Built from the PARSED dates (like the Python original's
  // parsed_from.date()), never the raw query strings — keeps
  // attacker-influenced text out of the Content-Disposition header.
  const filename = `vitalnet_cases_${parsedFrom.toISOString().slice(0, 10)}_${parsedTo.toISOString().slice(0, 10)}.csv`;
  return c.body(csv, 200, {
    "Content-Type": "text/csv",
    "Content-Disposition": `attachment; filename="${filename}"`,
  });
});
