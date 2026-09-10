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
import { getClientIp } from "./audit.ts";

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
  return `ip:${getClientIp(c)}`;
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
      // Fail closed: if the shared rate-limit store is unavailable, continuing
      // would silently disable abuse protection on every Edge isolate. The
      // Edge backend is not live yet, so callers can retry after the store is
      // healthy rather than receiving an unprotected request path.
      console.error("fn_rate_limit call failed", error);
      return c.json({ detail: "Rate limit service unavailable" }, 503);
    }

    if (data !== true) {
      return c.json({ detail: "Rate limit exceeded" }, 429);
    }
    await next();
  };
}
