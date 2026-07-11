// Ported from CorrelationIdMiddleware (app/main.py) — propagates/generates
// X-Request-ID for tracing across logs and responses. Hono's Context is
// request-scoped and passed explicitly through the whole chain, so this
// needs no Python-style contextvar: c.set/c.get IS the per-request store.
import type { Context, Next } from "hono";

export async function correlationId(c: Context, next: Next) {
  const id = c.req.header("X-Request-ID") || crypto.randomUUID();
  c.set("correlationId", id);
  await next();
  c.res.headers.set("X-Request-ID", id);
}
