// getClientIp only — logPhiAccess needs a live Supabase client (it writes
// via getSupabaseAdmin()), not exercised here for the same reason
// auth.test.ts skips the JWKS network path: keep this suite fast and
// network-independent.
import { assertEquals } from "@std/assert";
import { Hono } from "hono";
import { getClientIp } from "../_shared/audit.ts";

async function ipFromHeaders(headers: Record<string, string>): Promise<string> {
  const app = new Hono();
  let captured = "";
  app.get("/x", (c) => {
    captured = getClientIp(c);
    return c.text("ok");
  });
  await app.request("/x", { headers });
  return captured;
}

Deno.test("getClientIp: prefers x-forwarded-for, first entry only", async () => {
  assertEquals(await ipFromHeaders({ "x-forwarded-for": "203.0.113.5, 10.0.0.1" }), "203.0.113.5");
});

Deno.test("getClientIp: falls back to x-real-ip", async () => {
  assertEquals(await ipFromHeaders({ "x-real-ip": "203.0.113.9" }), "203.0.113.9");
});

Deno.test("getClientIp: unknown when neither header is present", async () => {
  assertEquals(await ipFromHeaders({}), "unknown");
});
