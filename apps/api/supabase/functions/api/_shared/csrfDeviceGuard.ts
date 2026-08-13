// Ported verbatim from csrf_and_device_guard (app/main.py). Bearer-token
// auth already stops cross-site forms from acting as an authenticated
// user; requiring a custom header on every mutating request adds defense
// in depth — a browser only sends a custom header after a CORS preflight,
// and the preflight only succeeds from an allow_origins match. The header
// value itself is not a secret — the protection is the preflight gate.
import type { Context, Next } from "hono";
import { getConfig } from "./config.ts";

const STATE_CHANGING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function csrfAndDeviceGuard(c: Context, next: Next) {
  const path = new URL(c.req.url).pathname;
  if (path.startsWith("/api") && STATE_CHANGING_METHODS.has(c.req.method.toUpperCase())) {
    const authHeader = c.req.header("authorization");
    if (authHeader) {
      const csrfHeader = c.req.header("x-csrf-token") ?? "";
      if (csrfHeader !== getConfig().csrfToken) {
        return c.json({ detail: "CSRF token missing or invalid" }, 403);
      }
      if (!c.req.header("x-device-id")) {
        return c.json({ detail: "Missing X-Device-Id header" }, 400);
      }
    }
  }
  await next();
}
