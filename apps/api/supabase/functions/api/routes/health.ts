// Ported from the /api/health handler in app/main.py. One behavioral
// difference from the Python original, noted rather than silently
// dropped: that version reports whether the server-side ML classifier is
// "loaded" (a boot-time lifespan step). This edge function has no
// boot-time model load — triage is either clinical-core's pure rules
// engine (always available, nothing to load) or the advisory tree model
// evaluated per-request from a static JSON bundle the frontend fetches
// directly — so there is no equivalent "loaded/not loaded" state to
// report here. The authenticated-diagnostics path reports that fact
// plainly instead of a loaded flag.
import { Hono } from "hono";
import { getCurrentUser } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseAnon } from "../_shared/database.ts";

export const health = new Hono();

const VERSION = "0.4.0"; // apps/api — tracks the Tranche A/B port, independent of the legacy backend's version.

health.get("/api/health", rateLimit(120, 60), async (c) => {
  let dbStatus: "connected" | "error" = "connected";
  try {
    const { error } = await getSupabaseAnon().from("facilities").select("id").limit(1);
    if (error) throw error;
  } catch (e) {
    console.warn("Health check DB connectivity failed:", e);
    dbStatus = "error";
  }

  const isHealthy = dbStatus === "connected";

  let showDiagnostics = false;
  const authorization = c.req.header("authorization");
  if (authorization) {
    try {
      const user = await getCurrentUser(authorization);
      if (user.resolvedRole === "doctor" || user.resolvedRole === "admin") {
        showDiagnostics = true;
      }
    } catch {
      // Fall back to the anonymous (basic) response on auth failure.
    }
  }

  const body = showDiagnostics
    ? {
      status: isHealthy ? "ok" : "degraded",
      database: dbStatus,
      triage: "clinical-core rules_first",
      version: VERSION,
    }
    : { status: isHealthy ? "ok" : "degraded", version: VERSION };

  return c.json(body, isHealthy ? 200 : 503);
});
