// Ported from metrics_routes.py's GET /api/metrics — admin-only, same
// access-control posture as the rest of the admin surface. Only
// vitalnet_triage_classifications_total is ported here; see
// backend/supabase/migrations/phase30_triage_metrics_fn.sql's header for
// why the HTTP request-rate/latency metrics are a deliberate, documented
// gap rather than a silent omission (they'd need a new per-request write
// path, not just a read).
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { type CounterSample, PROMETHEUS_CONTENT_TYPE, renderCounter } from "../_shared/prometheus.ts";
import type { AppEnv } from "../_shared/types.ts";

export const metrics = new Hono<AppEnv>();

interface TriageMetricsRow {
  triage_level: string;
  count: number;
}

metrics.get("/api/metrics", rateLimit(60, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const db = getSupabaseForUser(user.token);

  const { data, error } = await db.rpc("fn_triage_metrics", {});
  if (error) {
    console.warn("Triage metrics query failed:", error);
    throw new HttpError(502, "Metrics query failed — try again");
  }

  const samples: CounterSample[] = ((data ?? []) as TriageMetricsRow[]).map((row) => ({
    labels: { triage_level: row.triage_level },
    value: row.count,
  }));

  const body = renderCounter(
    "vitalnet_triage_classifications_total",
    "Triage classifications produced, by level",
    samples,
  );

  return c.body(body, 200, { "Content-Type": PROMETHEUS_CONTENT_TYPE });
});
