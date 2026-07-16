// VitalNet API — Edge Function entrypoint (Round 6 rebuild plan, Phase 3
// Tranche A). One Hono app, deployed as the single "api" Supabase Edge
// Function (the official Supabase pattern — one function, Hono router
// inside — rather than one function per route, which would multiply cold
// starts).
//
// Middleware ordering note: Hono runs app.use() middleware in registration
// order (first registered = outermost). Starlette's add_middleware PREPENDS
// (last added = outermost), so app/main.py's *effective* order is the
// reverse of its source order. The registration order below reproduces the
// Python backend's effective order: CORS outermost, then response-header
// middleware (security headers / correlation id, order between them
// immaterial — they set disjoint headers), then the CSRF/device guard,
// then routes.
import { Hono } from "hono";
import { cors } from "hono/cors";
import { allowedOrigins, getConfig } from "./_shared/config.ts";
import { correlationId } from "./_shared/correlationId.ts";
import { securityHeaders } from "./_shared/securityHeaders.ts";
import { csrfAndDeviceGuard } from "./_shared/csrfDeviceGuard.ts";
import { stripFunctionPrefix } from "./_shared/functionPrefix.ts";
import { HttpError } from "./_shared/database.ts";
import { health } from "./routes/health.ts";
import { outbreak } from "./routes/outbreak.ts";
import { supervisor } from "./routes/supervisor.ts";
import { referral } from "./routes/referral.ts";
import { metrics } from "./routes/metrics.ts";
import { protocol } from "./routes/protocol.ts";
import { analytics } from "./routes/analytics.ts";
import { cases } from "./routes/cases.ts";
import { security } from "./routes/security.ts";
import { dsr } from "./routes/dsr.ts";
import { admin } from "./routes/admin.ts";
import { push } from "./routes/push.ts";
import { voice } from "./routes/voice.ts";
import type { AppEnv } from "./_shared/types.ts";

const app = new Hono<AppEnv>();

app.use(
  "*",
  cors({
    origin: (origin) => {
      const allowed = allowedOrigins(getConfig());
      // Only ever reflect an explicitly allow-listed origin. On any mismatch
      // return "" so no Access-Control-Allow-Origin is granted — never
      // default to allowed[0], which both reflected the wrong origin on a
      // mismatch and, if allowedOrigins() ever resolved empty in a
      // misconfigured env, handed every caller an empty ACAO. Matches the
      // Python original, which omits the header on a non-match.
      return origin && allowed.includes(origin) ? origin : "";
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
app.route("/", supervisor);
app.route("/", referral);
app.route("/", metrics);
app.route("/", protocol);
app.route("/", analytics);
// Tranche B (Phase 4, Round 6 rebuild plan) — writes + the rules-first flip.
app.route("/", cases);
app.route("/", security);
app.route("/", dsr);
app.route("/", admin);
app.route("/", push);
app.route("/", voice);

// The /functions/v1/api prefix must be stripped BEFORE Hono sees the
// request — Hono resolves the handler chain from the path before any
// middleware runs, so a rewrite inside app.use() is too late (the router
// has already 404'd). See _shared/functionPrefix.ts.
Deno.serve((req) => app.fetch(stripFunctionPrefix(req)));

export default app;
