// Hono app.request() contract tests (Round 6 rebuild plan, Phase 3
// verification item 2) — each middleware wrapped in a minimal Hono app
// and exercised via in-memory requests, no real server/network needed.
import { assertEquals } from "@std/assert";
import { Hono } from "hono";
import { correlationId } from "../_shared/correlationId.ts";
import { securityHeaders } from "../_shared/securityHeaders.ts";
import { csrfAndDeviceGuard } from "../_shared/csrfDeviceGuard.ts";
import { _setConfigForTest, type Config } from "../_shared/config.ts";

function testConfig(overrides: Partial<Config> = {}): Config {
  return {
    supabaseUrl: "https://example.supabase.co",
    supabaseAnonKey: "anon",
    supabaseJwtSecret: "secret",
    supabaseServiceRoleKey: "service",
    environment: "development",
    corsAllowedOrigins: "",
    frontendUrl: "",
    jwtLocalVerification: true,
    revocationRecheckSeconds: 300,
    csrfToken: "vitalnet-spa",
    groqApiKey: "",
    geminiApiKey: "",
    sarvamApiKey: "",
    vapidPublicKey: "",
    vapidPrivateKey: "",
    vapidSubject: "mailto:admin@example.com",
    dataRetentionDays: 0,
    ...overrides,
  };
}

// ── correlationId ────────────────────────────────────────────────────────────

Deno.test("correlationId: generates an id when none supplied", async () => {
  const app = new Hono();
  app.use("*", correlationId);
  app.get("/x", (c) => c.text("ok"));

  const res = await app.request("/x");
  const id = res.headers.get("X-Request-ID");
  if (!id) throw new Error("expected X-Request-ID header");
  assertEquals(id.length > 0, true);
});

Deno.test("correlationId: echoes a supplied id", async () => {
  const app = new Hono();
  app.use("*", correlationId);
  app.get("/x", (c) => c.text("ok"));

  const res = await app.request("/x", { headers: { "X-Request-ID": "trace-42" } });
  assertEquals(res.headers.get("X-Request-ID"), "trace-42");
});

// ── securityHeaders ───────────────────────────────────────────────────────────

Deno.test("securityHeaders: sets the standard hardening headers", async () => {
  _setConfigForTest(testConfig({ environment: "development" }));
  const app = new Hono();
  app.use("*", securityHeaders);
  app.get("/x", (c) => c.text("ok"));

  const res = await app.request("/x");
  assertEquals(res.headers.get("X-Content-Type-Options"), "nosniff");
  assertEquals(res.headers.get("X-Frame-Options"), "DENY");
  assertEquals(res.headers.get("Cache-Control"), "no-store");
  assertEquals(res.headers.get("Referrer-Policy"), "no-referrer");
});

Deno.test("securityHeaders: HSTS only outside development", async () => {
  _setConfigForTest(testConfig({ environment: "development" }));
  const devApp = new Hono();
  devApp.use("*", securityHeaders);
  devApp.get("/x", (c) => c.text("ok"));
  const devRes = await devApp.request("/x");
  assertEquals(devRes.headers.get("Strict-Transport-Security"), null);

  _setConfigForTest(testConfig({ environment: "production" }));
  const prodApp = new Hono();
  prodApp.use("*", securityHeaders);
  prodApp.get("/x", (c) => c.text("ok"));
  const prodRes = await prodApp.request("/x");
  if (!prodRes.headers.get("Strict-Transport-Security")) {
    throw new Error("expected Strict-Transport-Security header in production");
  }
});

// ── csrfAndDeviceGuard ─────────────────────────────────────────────────────────

function csrfApp() {
  const app = new Hono();
  app.use("*", csrfAndDeviceGuard);
  app.post("/api/x", (c) => c.text("ok"));
  app.get("/api/x", (c) => c.text("ok"));
  return app;
}

Deno.test("csrfAndDeviceGuard: GET requests are never guarded", async () => {
  _setConfigForTest(testConfig());
  const res = await csrfApp().request("/api/x", { method: "GET" });
  assertEquals(res.status, 200);
});

Deno.test("csrfAndDeviceGuard: POST without an Authorization header is not guarded (no session to forge)", async () => {
  _setConfigForTest(testConfig());
  const res = await csrfApp().request("/api/x", { method: "POST" });
  assertEquals(res.status, 200);
});

Deno.test("csrfAndDeviceGuard: authenticated POST without CSRF token is rejected", async () => {
  _setConfigForTest(testConfig());
  const res = await csrfApp().request("/api/x", {
    method: "POST",
    headers: { Authorization: "Bearer x.y.z" },
  });
  assertEquals(res.status, 403);
});

Deno.test("csrfAndDeviceGuard: authenticated POST with wrong CSRF token is rejected", async () => {
  _setConfigForTest(testConfig());
  const res = await csrfApp().request("/api/x", {
    method: "POST",
    headers: { Authorization: "Bearer x.y.z", "X-CSRF-Token": "wrong" },
  });
  assertEquals(res.status, 403);
});

Deno.test("csrfAndDeviceGuard: correct CSRF token but missing device id is rejected", async () => {
  _setConfigForTest(testConfig());
  const res = await csrfApp().request("/api/x", {
    method: "POST",
    headers: { Authorization: "Bearer x.y.z", "X-CSRF-Token": "vitalnet-spa" },
  });
  assertEquals(res.status, 400);
});

Deno.test("csrfAndDeviceGuard: correct CSRF token + device id passes", async () => {
  _setConfigForTest(testConfig());
  const res = await csrfApp().request("/api/x", {
    method: "POST",
    headers: {
      Authorization: "Bearer x.y.z",
      "X-CSRF-Token": "vitalnet-spa",
      "X-Device-Id": "device-1",
    },
  });
  assertEquals(res.status, 200);
});

Deno.test("csrfAndDeviceGuard: non-/api paths are never guarded", async () => {
  _setConfigForTest(testConfig());
  const app = new Hono();
  app.use("*", csrfAndDeviceGuard);
  app.post("/other", (c) => c.text("ok"));
  const res = await app.request("/other", {
    method: "POST",
    headers: { Authorization: "Bearer x.y.z" },
  });
  assertEquals(res.status, 200);
});
