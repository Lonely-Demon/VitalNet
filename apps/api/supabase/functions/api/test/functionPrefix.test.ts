import { assertEquals } from "@std/assert";
import { Hono } from "hono";
import { stripFunctionPrefix } from "../_shared/functionPrefix.ts";

Deno.test("stripFunctionPrefix: strips the Supabase invoke prefix", () => {
  const req = new Request("https://x.supabase.co/functions/v1/api/api/health?q=1");
  const out = stripFunctionPrefix(req);
  assertEquals(new URL(out.url).pathname, "/api/health");
  assertEquals(new URL(out.url).search, "?q=1");
});

Deno.test("stripFunctionPrefix: bare prefix maps to /", () => {
  const req = new Request("https://x.supabase.co/functions/v1/api");
  assertEquals(new URL(stripFunctionPrefix(req).url).pathname, "/");
});

Deno.test("stripFunctionPrefix: unprefixed request passes through unchanged", () => {
  const req = new Request("https://x.supabase.co/api/health");
  assertEquals(stripFunctionPrefix(req), req);
});

Deno.test("stripFunctionPrefix: a function named api-something is not mangled", () => {
  const req = new Request("https://x.supabase.co/functions/v1/apiv2/api/health");
  assertEquals(new URL(stripFunctionPrefix(req).url).pathname, "/functions/v1/apiv2/api/health");
});

Deno.test("stripFunctionPrefix: method, headers, and body survive the rewrite", async () => {
  const req = new Request("https://x.supabase.co/functions/v1/api/api/submit", {
    method: "POST",
    headers: { "X-CSRF-Token": "t", "Content-Type": "application/json" },
    body: JSON.stringify({ a: 1 }),
  });
  const out = stripFunctionPrefix(req);
  assertEquals(out.method, "POST");
  assertEquals(out.headers.get("X-CSRF-Token"), "t");
  assertEquals(await out.json(), { a: 1 });
});

// The regression case: this MUST go through a real Hono router, because
// the original implementation (a rewrite inside app.use()) passed every
// pure-function test imaginable while every prefixed request 404'd — Hono
// resolves the handler chain from the path before middleware runs.
Deno.test("routing integration: a prefixed request reaches the route", async () => {
  const app = new Hono();
  app.get("/api/health", (c) => c.text("reached"));

  const direct = await app.fetch(stripFunctionPrefix(new Request("http://localhost/api/health")));
  assertEquals(direct.status, 200);

  const prefixed = await app.fetch(stripFunctionPrefix(new Request("http://localhost/functions/v1/api/api/health")));
  assertEquals(prefixed.status, 200);
  assertEquals(await prefixed.text(), "reached");
});
