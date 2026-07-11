// VitalNet API — Edge Function entrypoint (Round 6 rebuild plan, Phase 3
// Tranche A). One Hono app, deployed as the single "api" Supabase Edge
// Function (the official Supabase pattern — one function, Hono router
// inside — rather than one function per route, which would multiply cold
// starts). Middleware order mirrors app/main.py's registration order
// exactly, since Starlette/Hono both apply middleware in registration
// order and several of these depend on running before/after specific
// others (CORS must wrap everything; security headers/correlation id
// should apply to error responses too, so they wrap the router).
import { Hono } from "hono";
import { cors } from "hono/cors";
import { allowedOrigins, getConfig } from "./_shared/config.ts";
import { correlationId } from "./_shared/correlationId.ts";
import { securityHeaders } from "./_shared/securityHeaders.ts";
import { csrfAndDeviceGuard } from "./_shared/csrfDeviceGuard.ts";
import { HttpError } from "./_shared/database.ts";
import { health } from "./routes/health.ts";
import { outbreak } from "./routes/outbreak.ts";
import type { AppEnv } from "./_shared/types.ts";

const app = new Hono<AppEnv>();

// Supabase invokes every edge function behind a path prefix
// (/functions/v1/<function-name>); strip it so route definitions below
// can use the same /api/... paths the legacy backend and the frontend
// already agree on.
app.use("*", async (c, next) => {
  const url = new URL(c.req.url);
  const stripped = url.pathname.replace(/^\/functions\/v1\/api/, "") || "/";
  if (stripped !== url.pathname) {
    c.req.raw = new Request(new URL(stripped + url.search, url), c.req.raw);
  }
  await next();
});

app.use(
  "*",
  cors({
    origin: (origin) => {
      const allowed = allowedOrigins(getConfig());
      return origin && allowed.includes(origin) ? origin : allowed[0] ?? "";
    },
    credentials: true,
    allowMethods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowHeaders: ["Authorization", "Content-Type", "X-CSRF-Token", "X-Device-Id", "X-Request-ID"],
  }),
);

app.use("*", securityHeaders);
app.use("*", correlationId);
app.use("*", csrfAndDeviceGuard);

app.onError((err, c) => {
  if (err instanceof HttpError) {
    return c.json({ detail: err.message }, err.status as 400 | 401 | 403 | 404 | 429 | 500);
  }
  console.error("Unhandled server error:", err);
  return c.json({ detail: "Internal Server Error" }, 500);
});

app.notFound((c) => c.json({ detail: "Not Found" }, 404));

app.route("/", health);
app.route("/", outbreak);

Deno.serve(app.fetch);

export default app;
