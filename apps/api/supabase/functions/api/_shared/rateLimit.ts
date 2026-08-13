// Postgres-backed rate limiting via fn_rate_limit (backend/supabase/
// migrations/phase28_security_definer_fns.sql) — replaces slowapi, whose
// in-memory store doesn't survive an edge isolate being recycled between
// requests (see that migration's header). Keyed on a LOCALLY-verified
// user id when present (never a client-asserted one — see
// verifiedSubForRateLimit), falling back to client IP, same as
// verify_sub_for_rate_limit's usage in the Python routes.
import type { Context, Next } from "hono";
import { getSupabaseAnon } from "./database.ts";
import { verifiedSubForRateLimit } from "./auth.ts";

async function rateLimitKey(c: Context): Promise<string> {
  const auth = c.req.header("authorization");
  if (auth) {
    const match = /^Bearer\s+(.+)$/i.exec(auth);
    const token = match?.[1];
    if (token) {
      const sub = await verifiedSubForRateLimit(token);
      if (sub) return `user:${sub}`;
    }
  }
  const forwardedFor = c.req.header("x-forwarded-for");
  const ip = forwardedFor?.split(",")[0]?.trim() || c.req.header("x-real-ip") || "unknown";
  return `ip:${ip}`;
}

/** Hono middleware factory. Usage: app.get("/api/x", rateLimit(60, 60), handler) */
export function rateLimit(max: number, windowSeconds: number) {
  return async (c: Context, next: Next) => {
    const key = await rateLimitKey(c);
    const db = getSupabaseAnon();
    const { data, error } = await db.rpc("fn_rate_limit", {
      p_key: key,
      p_max: max,
      p_window_s: windowSeconds,
    });

    if (error) {
      // Fail open on an infra error — a rate-limit-store hiccup should not
      // 500 the whole API. Logged so a persistent failure is visible.
      console.error("fn_rate_limit call failed", error);
      await next();
      return;
    }

    if (data !== true) {
      return c.json({ detail: "Rate limit exceeded" }, 429);
    }
    await next();
  };
}
