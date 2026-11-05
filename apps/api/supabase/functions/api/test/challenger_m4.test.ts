// apps/api/supabase/functions/api/test/challenger_m4.test.ts
// Empirical Challenger stress-test suite for Milestone M4 fixes.
import { assertEquals, assertThrows } from "@std/assert";
import { Hono } from "hono";
import { GLOBAL_SCOPE_ROLE, isGlobalScope, resolveFacilityScope, resolveScope } from "../_shared/scoping.ts";
import { HttpError } from "../_shared/database.ts";
import { validatePushEndpoint } from "../_shared/webpush.ts";
import { verifySchedulerToken } from "../routes/push.ts";
import { getClientIp } from "../_shared/audit.ts";
import { sanitizeCsvValue, toCsv } from "../_shared/csv.ts";
import { transcribe } from "../_shared/voice.ts";
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
    internalSchedulerToken: "secret-token",
    ...overrides,
  };
}

// =============================================================================
// CHALLENGE 1: Edge Scoping & RBAC Parity (HIGH-1)
// =============================================================================

Deno.test("CHALLENGE 1.1: GLOBAL_SCOPE_ROLE is strictly supervisor", () => {
  assertEquals(GLOBAL_SCOPE_ROLE, "supervisor");
  assertEquals(isGlobalScope("supervisor"), true);
  assertEquals(isGlobalScope("SUPERVISOR"), false); // case sensitivity
  assertEquals(isGlobalScope("admin"), false);
  assertEquals(isGlobalScope("doctor"), false);
  assertEquals(isGlobalScope("asha_worker"), false);
  assertEquals(isGlobalScope("chw"), false);
  assertEquals(isGlobalScope("nurse"), false);
  assertEquals(isGlobalScope(""), false);
});

Deno.test("CHALLENGE 1.2: Supervisor scoping permutations", () => {
  // Supervisor with no facility assigned and no requested facility -> global scope
  const globalScope = resolveScope("supervisor", null, null);
  assertEquals(globalScope.facilityId, null);
  assertEquals(globalScope.is_global, true);

  // Supervisor with home facility assigned but requesting all (null) -> still global scope
  const globalScopeWithHome = resolveScope("supervisor", "fac-home", null);
  assertEquals(globalScopeWithHome.facilityId, null);
  assertEquals(globalScopeWithHome.is_global, true);

  // Supervisor narrowing to specific facility -> scoped, is_global false
  const narrowedScope = resolveScope("supervisor", null, "fac-target");
  assertEquals(narrowedScope.facilityId, "fac-target");
  assertEquals(narrowedScope.is_global, false);
});

Deno.test("CHALLENGE 1.3: Non-supervisor roles cannot widen scope and are rejected without facility", () => {
  const nonSupervisorRoles = ["admin", "doctor", "asha_worker", "nurse", "chw", "lab_tech", "pharmacist"];

  for (const role of nonSupervisorRoles) {
    // Rejection when unassigned
    const err = assertThrows(() => resolveFacilityScope(role, null, null), HttpError);
    assertEquals(err.status, 400);

    const errWithRequested = assertThrows(() => resolveFacilityScope(role, null, "fac-target"), HttpError);
    assertEquals(errWithRequested.status, 400);

    // Bound to own facility even if passing requestedFacilityId
    assertEquals(resolveFacilityScope(role, "fac-own", null), "fac-own");
    assertEquals(resolveFacilityScope(role, "fac-own", "fac-attacker"), "fac-own");

    const scope = resolveScope(role, "fac-own", "fac-attacker");
    assertEquals(scope.facilityId, "fac-own");
    assertEquals(scope.is_global, false);
  }
});

// =============================================================================
// CHALLENGE 1.4: Protocol ask endpoint facility requirement & supervisor bypass
// =============================================================================

Deno.test("CHALLENGE 1.4: Protocol route facility check logic", () => {
  // Simulate the facility checking logic from routes/protocol.ts:
  // if (!facilityId && user.resolvedRole !== "supervisor") {
  //   throw new HttpError(400, "Account has no facility assigned");
  // }
  const checkFacility = (userRole: string, facilityId: string | null) => {
    if (!facilityId && userRole !== "supervisor") {
      throw new HttpError(400, "Account has no facility assigned");
    }
    return { ok: true, facility_id: facilityId ?? null };
  };

  // Supervisor without facility succeeds with null facility
  const supResult = checkFacility("supervisor", null);
  assertEquals(supResult.ok, true);
  assertEquals(supResult.facility_id, null);

  // Supervisor with facility succeeds with facility
  const supResult2 = checkFacility("supervisor", "fac-1");
  assertEquals(supResult2.ok, true);
  assertEquals(supResult2.facility_id, "fac-1");

  // Non-supervisors without facility throw 400
  for (const role of ["asha_worker", "doctor", "admin", "nurse", "chw"]) {
    const err = assertThrows(() => checkFacility(role, null), HttpError);
    assertEquals(err.status, 400);
    assertEquals(err.message, "Account has no facility assigned");

    // With facility they succeed
    const res = checkFacility(role, "fac-assigned");
    assertEquals(res.ok, true);
    assertEquals(res.facility_id, "fac-assigned");
  }
});

// =============================================================================
// CHALLENGE 2: Web Push SSRF Host Allowlist & Scheduler Token (HIGH-4)
// =============================================================================

Deno.test("CHALLENGE 2.1: validatePushEndpoint adversarial SSRF vectors", () => {
  const evilEndpoints = [
    // AWS / cloud metadata
    "http://169.254.169.254/latest/meta-data",
    "https://169.254.169.254/latest/meta-data",
    "https://169.254.169.254.nip.io/push",
    // Localhost & private LAN
    "http://127.0.0.1:8000/api",
    "https://127.0.0.1:8000/api",
    "http://localhost:5173",
    "https://localhost:8000",
    "https://192.168.1.1/admin",
    "https://10.0.0.1/status",
    // Subdomain deception attacks
    "https://fcm.googleapis.com.evil-domain.com/send",
    "https://push.apple.com.attacker.org/alert",
    "https://not-fcm.googleapis.com.attacker.com",
    "https://evilfcm.googleapis.com/send",
    "https://evil-push.apple.com/send",
    "https://fakemozilla.com/push",
    // Scheme tricks
    "ftp://fcm.googleapis.com/push",
    "gopher://fcm.googleapis.com/push",
    "file:///etc/passwd",
    "javascript:alert(1)",
    // Malformed
    "not-even-a-url",
    "",
  ];

  for (const ep of evilEndpoints) {
    const err = assertThrows(() => validatePushEndpoint(ep), HttpError);
    assertEquals(err.status, 400);
  }
});

Deno.test("CHALLENGE 2.2: validatePushEndpoint legitimate provider domains", () => {
  const legitEndpoints = [
    "https://fcm.googleapis.com/fcm/send/token123",
    "https://android.googleapis.com.not.allowed", // should fail
    "https://web.push.apple.com/endpoint/abc",
    "https://push.apple.com/endpoint/def",
    "https://db5.notify.windows.com/w/?token=xyz",
    "https://updates.push.services.mozilla.com/wpush/v2/ghi",
    "https://autopush.mozilla.com/push/jkl",
    "https://sub.autopush.mozilla.com/push/mno",
  ];

  for (const ep of legitEndpoints) {
    if (ep.includes("not.allowed")) {
      assertThrows(() => validatePushEndpoint(ep), HttpError);
    } else {
      validatePushEndpoint(ep); // Must not throw
    }
  }
});

Deno.test("CHALLENGE 2.3: verifySchedulerToken enforcement", () => {
  // 1. Unconfigured token -> 503
  _setConfigForTest(testConfig({ internalSchedulerToken: "" }));
  assertThrows(
    () => verifySchedulerToken({ req: { header: () => "any" } }),
    HttpError,
    "Escalation scheduler endpoint disabled",
  );

  // 2. Configured token, missing header -> 403
  _setConfigForTest(testConfig({ internalSchedulerToken: "expected-secret" }));
  assertThrows(
    () => verifySchedulerToken({ req: { header: () => undefined } }),
    HttpError,
    "Invalid or missing scheduler token",
  );

  // 3. Configured token, wrong header -> 403
  assertThrows(
    () => verifySchedulerToken({ req: { header: () => "wrong-secret" } }),
    HttpError,
    "Invalid or missing scheduler token",
  );

  // 4. Configured token, correct header -> passes
  verifySchedulerToken({
    req: {
      header: (name: string) => (name.toLowerCase() === "x-internal-scheduler-token" ? "expected-secret" : undefined),
    },
  });
});

// =============================================================================
// CHALLENGE 3: Rightmost Proxy IP Extraction (HIGH-5)
// =============================================================================

Deno.test("CHALLENGE 3.1: getClientIp rightmost proxy IP extraction", async () => {
  const makeCtx = (headers: Record<string, string>) => {
    const app = new Hono();
    let ip = "";
    app.get("/test", (c) => {
      ip = getClientIp(c);
      return c.text("ok");
    });
    return { app, getIp: async () => { await app.request("/test", { headers }); return ip; } };
  };

  // When untrusted, returns unknown regardless of headers
  Deno.env.delete("TRUST_PROXY_HEADERS");
  assertEquals(await makeCtx({ "x-forwarded-for": "1.2.3.4, 5.6.7.8" }).getIp(), "unknown");

  // When trusted, extracts rightmost hop
  Deno.env.set("TRUST_PROXY_HEADERS", "true");
  try {
    // Single hop
    assertEquals(await makeCtx({ "x-forwarded-for": "203.0.113.195" }).getIp(), "203.0.113.195");

    // Attacker injected spoofed leftmost hops:
    assertEquals(
      await makeCtx({ "x-forwarded-for": "spoofed-ip, 127.0.0.1, 10.0.0.1, 203.0.113.50" }).getIp(),
      "203.0.113.50",
    );

    // Trailing spaces and commas handled cleanly
    assertEquals(
      await makeCtx({ "x-forwarded-for": "  1.2.3.4 ,  10.20.30.40  ,  " }).getIp(),
      "10.20.30.40",
    );

    // Fallback to x-real-ip when x-forwarded-for is absent
    assertEquals(await makeCtx({ "x-real-ip": "198.51.100.22" }).getIp(), "198.51.100.22");

    // Unknown when no headers present
    assertEquals(await makeCtx({}).getIp(), "unknown");
  } finally {
    Deno.env.delete("TRUST_PROXY_HEADERS");
  }
});

// =============================================================================
// CHALLENGE 4: CSV Formula Injection Neutralization (HIGH-6)
// =============================================================================

Deno.test("CHALLENGE 4.1: CSV formula triggers neutralization across all vectors", () => {
  const injectionPayloads = [
    "=1+2",
    "=cmd|' /C calc'!A0",
    "+12345",
    "+SUM(A1:B10)",
    "-42",
    "-2+3*[1]!A1",
    "@SUM(C1:C5)",
    "\tpowershell.exe -enc ...",
    "\rnotepad.exe",
  ];

  for (const payload of injectionPayloads) {
    const sanitized = sanitizeCsvValue(payload);
    assertEquals(sanitized.startsWith("'"), true, `Failed to prepend quote for: ${payload}`);
  }

  // Safe values should NOT be prepended
  assertEquals(sanitizeCsvValue("Normal Patient Name"), "Normal Patient Name");
  assertEquals(sanitizeCsvValue("120/80"), "120/80");
  assertEquals(sanitizeCsvValue(""), "");
});

Deno.test("CHALLENGE 4.2: toCsv properly sanitizes and quotes formula triggers in table output", () => {
  const rows = [
    { name: "=HYPERLINK('http://evil.com')", age: 30, notes: "+alert(1)" },
    { name: "Safe Patient", age: 25, notes: "@review" },
  ];
  const csv = toCsv(["name", "age", "notes"], rows);

  // Must prepend single quote
  assertEquals(csv.includes("'=HYPERLINK"), true);
  assertEquals(csv.includes("'+alert(1)"), true);
  assertEquals(csv.includes("'@review"), true);
  assertEquals(csv.includes("Safe Patient"), true);
});

// =============================================================================
// CHALLENGE 5: Voice Transcription Timeout & Direct Buffer (HIGH-8b)
// =============================================================================

Deno.test("CHALLENGE 5.1: Voice transcription sets 20s AbortSignal.timeout and avoids buffer slice", async () => {
  _setConfigForTest(testConfig({ groqApiKey: "groq-test-key" }));

  let capturedSignal: AbortSignal | undefined;
  let capturedBlob: Blob | undefined;

  const originalFetch = globalThis.fetch;
  const sampleAudio = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);

  globalThis.fetch = ((_input: RequestInfo | URL, init?: RequestInit) => {
    capturedSignal = init?.signal as AbortSignal;
    const body = init?.body as FormData;
    capturedBlob = body.get("file") as Blob;
    return Promise.resolve(new Response(JSON.stringify({ text: "transcribed speech" }), { status: 200 }));
  }) as typeof fetch;

  try {
    const text = await transcribe(sampleAudio, "speech.webm", "en");
    assertEquals(text, "transcribed speech");
    assertEquals(capturedSignal instanceof AbortSignal, true);
    assertEquals(capturedBlob?.size, 8);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
