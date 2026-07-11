// Ported verbatim from the security_headers middleware in app/main.py.
// Cache-Control: no-store is deliberate — API responses carry patient
// data and must never be cached by intermediaries or the browser. HSTS
// is only added outside local development.
import type { Context, Next } from "hono";
import { getConfig } from "./config.ts";

export async function securityHeaders(c: Context, next: Next) {
  await next();
  const h = c.res.headers;
  h.set("X-Content-Type-Options", "nosniff");
  h.set("X-Frame-Options", "DENY");
  h.set("Referrer-Policy", "no-referrer");
  h.set("Cache-Control", "no-store");
  if (!h.has("Permissions-Policy")) h.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  if (!h.has("Cross-Origin-Resource-Policy")) h.set("Cross-Origin-Resource-Policy", "same-site");
  if (!h.has("X-Permitted-Cross-Domain-Policies")) h.set("X-Permitted-Cross-Domain-Policies", "none");
  if (!h.has("Content-Security-Policy")) {
    h.set("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'self'");
  }
  if (getConfig().environment !== "development") {
    h.set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload");
  }
}
