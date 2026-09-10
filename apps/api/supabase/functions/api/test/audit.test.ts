// These tests are network-independent: getClientIp only reads request headers
// and the explicit trusted-proxy environment switch.
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

Deno.test("getClientIp: ignores forwarding headers by default", async () => {
  Deno.env.delete("TRUST_PROXY_HEADERS");
  assertEquals(await ipFromHeaders({ "x-forwarded-for": "203.0.113.5, 10.0.0.1" }), "unknown");
  assertEquals(await ipFromHeaders({ "x-real-ip": "203.0.113.9" }), "unknown");
});

Deno.test("getClientIp: uses proxy headers only when explicitly trusted", async () => {
  Deno.env.set("TRUST_PROXY_HEADERS", "true");
  try {
    assertEquals(await ipFromHeaders({ "x-forwarded-for": "203.0.113.5, 10.0.0.1" }), "203.0.113.5");
    assertEquals(await ipFromHeaders({ "x-real-ip": "203.0.113.9" }), "203.0.113.9");
  } finally {
    Deno.env.delete("TRUST_PROXY_HEADERS");
  }
});

Deno.test("getClientIp: unknown when no trusted header is present", async () => {
  Deno.env.delete("TRUST_PROXY_HEADERS");
  assertEquals(await ipFromHeaders({}), "unknown");
});
