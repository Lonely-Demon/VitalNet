// Tests for _shared/idempotency.ts. The replay/record paths need a live
// Supabase project (client_events + fn_client_event_record) to exercise
// for real — deliberately NOT covered here, same posture as
// test/auth.test.ts's JWKS/ES256 gap (see that file's header). What IS
// network-independent, and is covered here via Hono's app.request()
// in-memory contract-test pattern (test/middleware.test.ts's style): the
// no-op pass-through contract when no valid X-Event-Id is present — this
// path returns before ever constructing a Supabase client, so every
// caller that doesn't send the header (or sends a malformed one) must be
// completely unaffected by this middleware being attached.
import { assertEquals } from "@std/assert";
import { Hono } from "hono";
import { idempotent } from "../_shared/idempotency.ts";

function buildApp() {
  const app = new Hono();
  app.post("/api/thing", idempotent("thing.created"), (c) => c.json({ handled: true }));
  return app;
}

Deno.test("idempotent: no X-Event-Id header runs the handler normally", async () => {
  const app = buildApp();
  const res = await app.request("/api/thing", { method: "POST" });
  assertEquals(res.status, 200);
  assertEquals(await res.json(), { handled: true });
});

Deno.test("idempotent: a malformed X-Event-Id (not a UUID) runs the handler normally", async () => {
  const app = buildApp();
  const res = await app.request("/api/thing", {
    method: "POST",
    headers: { "X-Event-Id": "not-a-uuid" },
  });
  assertEquals(res.status, 200);
  assertEquals(await res.json(), { handled: true });
});
