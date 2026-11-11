// Tests for Web Push SSRF endpoint allowlist and scheduler token validation (HIGH-4)
import { assertEquals, assertThrows } from "@std/assert";
import { ALLOWED_PUSH_HOST_SUFFIXES, validatePushEndpoint } from "../_shared/webpush.ts";
import { HttpError } from "../_shared/database.ts";

Deno.test("ALLOWED_PUSH_HOST_SUFFIXES contains standard push providers", () => {
  assertEquals(ALLOWED_PUSH_HOST_SUFFIXES.includes(".fcm.googleapis.com"), true);
  assertEquals(ALLOWED_PUSH_HOST_SUFFIXES.includes(".push.apple.com"), true);
  assertEquals(ALLOWED_PUSH_HOST_SUFFIXES.includes(".notify.windows.com"), true);
  assertEquals(ALLOWED_PUSH_HOST_SUFFIXES.includes(".mozilla.com"), true);
  assertEquals(ALLOWED_PUSH_HOST_SUFFIXES.includes(".autopush.mozilla.com"), true);
});

Deno.test("validatePushEndpoint: accepts authorized HTTPS endpoints", () => {
  // Google FCM
  validatePushEndpoint("https://fcm.googleapis.com/fcm/send/sample-token");
  validatePushEndpoint("https://sub.fcm.googleapis.com/fcm/send/token2");

  // Apple APNs
  validatePushEndpoint("https://web.push.apple.com/sample-endpoint");
  validatePushEndpoint("https://push.apple.com/endpoint2");

  // Windows WNS
  validatePushEndpoint("https://wns2-sn1p.notify.windows.com/w/token3");

  // Mozilla
  validatePushEndpoint("https://updates.push.services.mozilla.com/wpush/v2/token4");
  validatePushEndpoint("https://sub.autopush.mozilla.com/push/token5");
});

Deno.test("validatePushEndpoint: rejects non-HTTPS endpoints", () => {
  const err = assertThrows(
    () => validatePushEndpoint("http://fcm.googleapis.com/fcm/send/sample-token"),
    HttpError,
  );
  assertEquals(err.status, 400);
  assertEquals(err.message.includes("HTTPS"), true);
});

Deno.test("validatePushEndpoint: rejects unauthorized push hosts (SSRF prevention)", () => {
  // Cloud metadata endpoint
  const errMeta = assertThrows(
    () => validatePushEndpoint("https://169.254.169.254/latest/meta-data"),
    HttpError,
  );
  assertEquals(errMeta.status, 400);

  // Localhost
  const errLocal = assertThrows(
    () => validatePushEndpoint("https://localhost:8000/internal"),
    HttpError,
  );
  assertEquals(errLocal.status, 400);

  // Attacker-controlled domain
  const errAttacker = assertThrows(
    () => validatePushEndpoint("https://evil-push-service.attacker.com/v1"),
    HttpError,
  );
  assertEquals(errAttacker.status, 400);

  // Subdomain masquerade attempt
  const errMasquerade = assertThrows(
    () => validatePushEndpoint("https://fcm.googleapis.com.attacker.com/send"),
    HttpError,
  );
  assertEquals(errMasquerade.status, 400);
});

Deno.test("validatePushEndpoint: rejects malformed endpoint URLs", () => {
  const err = assertThrows(
    () => validatePushEndpoint("not-a-valid-url"),
    HttpError,
  );
  assertEquals(err.status, 400);
});

// ── Scheduler token verification ─────────────────────────────────────────────

import { Hono } from "hono";
import { verifySchedulerToken } from "../routes/push.ts";
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
    vapidPublicKey: "fake-public",
    vapidPrivateKey: "fake-private",
    vapidSubject: "mailto:admin@example.com",
    dataRetentionDays: 0,
    internalSchedulerToken: "secret-scheduler-token",
    ...overrides,
  };
}

Deno.test("verifySchedulerToken: throws 503 when INTERNAL_SCHEDULER_TOKEN not configured", () => {
  _setConfigForTest(testConfig({ internalSchedulerToken: "" }));
  const mockContext = { req: { header: () => "any" } };
  const err = assertThrows(() => verifySchedulerToken(mockContext), HttpError);
  assertEquals(err.status, 503);
});

Deno.test("verifySchedulerToken: throws 403 when scheduler token is missing", () => {
  _setConfigForTest(testConfig({ internalSchedulerToken: "correct-secret" }));
  const mockContext = { req: { header: () => undefined } };
  const err = assertThrows(() => verifySchedulerToken(mockContext), HttpError);
  assertEquals(err.status, 403);
});

Deno.test("verifySchedulerToken: throws 403 when scheduler token is wrong", () => {
  _setConfigForTest(testConfig({ internalSchedulerToken: "correct-secret" }));
  const mockContext = { req: { header: () => "wrong-token" } };
  const err = assertThrows(() => verifySchedulerToken(mockContext), HttpError);
  assertEquals(err.status, 403);
});

Deno.test("verifySchedulerToken: passes when scheduler token matches", () => {
  _setConfigForTest(testConfig({ internalSchedulerToken: "correct-secret" }));
  const mockContext = {
    req: {
      header: (name: string) => (name.toLowerCase() === "x-internal-scheduler-token" ? "correct-secret" : undefined),
    },
  };
  verifySchedulerToken(mockContext);
});

Deno.test("check-emergency-escalations verifies scheduler token via Hono request", async () => {
  _setConfigForTest(testConfig({ internalSchedulerToken: "correct-secret" }));
  const app = new Hono();
  app.onError((err, c) => {
    if (err instanceof HttpError) return c.json({ detail: err.message }, err.status as 400 | 403 | 503);
    return c.json({ detail: "error" }, 500);
  });
  app.post("/api/push/check-emergency-escalations", (c) => {
    verifySchedulerToken(c);
    return c.json({ status: "checked" });
  });

  // Missing token -> 403
  const resMissing = await app.request("/api/push/check-emergency-escalations", { method: "POST" });
  assertEquals(resMissing.status, 403);

  // Wrong token -> 403
  const resWrong = await app.request("/api/push/check-emergency-escalations", {
    method: "POST",
    headers: { "x-internal-scheduler-token": "wrong" },
  });
  assertEquals(resWrong.status, 403);

  // Correct token -> 200
  const resCorrect = await app.request("/api/push/check-emergency-escalations", {
    method: "POST",
    headers: { "x-internal-scheduler-token": "correct-secret" },
  });
  assertEquals(resCorrect.status, 200);

  // Unconfigured token in env -> 503
  _setConfigForTest(testConfig({ internalSchedulerToken: "" }));
  const resDisabled = await app.request("/api/push/check-emergency-escalations", {
    method: "POST",
    headers: { "x-internal-scheduler-token": "correct-secret" },
  });
  assertEquals(resDisabled.status, 503);
});

// ── constantTimeEqual (BUG-58) ───────────────────────────────────────────────

import { constantTimeEqual } from "../routes/push.ts";

Deno.test("constantTimeEqual: handles identical and differing strings safely", () => {
  assertEquals(constantTimeEqual("secret-token-123", "secret-token-123"), true);
  assertEquals(constantTimeEqual("secret-token-123", "secret-token-124"), false);
  assertEquals(constantTimeEqual("short", "longer-string"), false);
  assertEquals(constantTimeEqual("", ""), true);
  assertEquals(constantTimeEqual("", "non-empty"), false);
});
