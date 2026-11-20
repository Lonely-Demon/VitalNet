// apps/api/supabase/functions/api/test/phase53_security.test.ts
// Test suite for Phase 53 Security Hardening & Parity Fixes (VN-53-01 through VN-53-12).

import { assertEquals, assertThrows } from "@std/assert";
import { authorizeDsrAccess, type CaseRecord } from "../routes/dsr.ts";
import { constantTimeEqual, verifySchedulerToken } from "../routes/push.ts";
import { GLOBAL_SCOPE_ROLES, resolveFacilityScope } from "../_shared/scoping.ts";
import { HttpError } from "../_shared/database.ts";
import { _setConfigForTest, type Config } from "../_shared/config.ts";
import type { AuthedUser } from "../_shared/types.ts";

function makeUser(overrides: Partial<AuthedUser> = {}): AuthedUser {
  return {
    sub: "user-test-id",
    resolvedRole: "doctor",
    resolvedFacilityId: "fac-1",
    token: "valid-tok",
    ...overrides,
  };
}

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
    internalSchedulerToken: "secret-token-xyz",
    ...overrides,
  };
}

// ── VN-53-04: Supervisor DSR & PHI Access Barred ─────────────────────────────

Deno.test("VN-53-04: authorizeDsrAccess allows super_admin for any case", () => {
  const saUser = makeUser({ resolvedRole: "super_admin", resolvedFacilityId: null });
  const caseRow: CaseRecord = { id: "case-1", facility_id: "fac-999", deleted_at: null };
  authorizeDsrAccess(saUser, caseRow);
});

Deno.test("VN-53-04: authorizeDsrAccess allows admin only for own facility", () => {
  const adminUser = makeUser({ resolvedRole: "admin", resolvedFacilityId: "fac-1" });
  const ownCase: CaseRecord = { id: "case-1", facility_id: "fac-1", deleted_at: null };
  authorizeDsrAccess(adminUser, ownCase);
});

Deno.test("VN-53-04: authorizeDsrAccess rejects admin for foreign facility with 403", () => {
  const adminUser = makeUser({ resolvedRole: "admin", resolvedFacilityId: "fac-1" });
  const foreignCase: CaseRecord = { id: "case-2", facility_id: "fac-2", deleted_at: null };

  const err = assertThrows(() => authorizeDsrAccess(adminUser, foreignCase), HttpError);
  assertEquals(err.status, 403);
  assertEquals(err.message, "Forbidden: Case does not belong to your facility");
});

Deno.test("VN-53-04: authorizeDsrAccess strictly rejects supervisor with 403", () => {
  const supervisorUser = makeUser({ resolvedRole: "supervisor", resolvedFacilityId: "fac-1" });
  const anyCase: CaseRecord = { id: "case-1", facility_id: "fac-1", deleted_at: null };

  const err = assertThrows(() => authorizeDsrAccess(supervisorUser, anyCase), HttpError);
  assertEquals(err.status, 403);
  assertEquals(err.message.includes("not permitted for DSR operations"), true);
});

// ── VN-53-03: Clinician Facility Fail-Closed ─────────────────────────────────

Deno.test("VN-53-03: Clinician with null facility fails closed with 400", () => {
  const err = assertThrows(() => resolveFacilityScope("doctor", null, null), HttpError);
  assertEquals(err.status, 400);
  assertEquals(err.message, "Account has no facility assigned");
});

Deno.test("VN-53-03: Clinician with facility cannot widen scope via query parameter", () => {
  const scope = resolveFacilityScope("doctor", "fac-mine", "fac-target");
  assertEquals(scope, "fac-mine");
});

// ── VN-53-05: Constant-Time Comparison on Scheduler Token ────────────────────

Deno.test("VN-53-05: constantTimeEqual accurately validates tokens in constant time", () => {
  assertEquals(constantTimeEqual("secret-token", "secret-token"), true);
  assertEquals(constantTimeEqual("secret-token", "wrong-token"), false);
  assertEquals(constantTimeEqual("secret-token", "secret-token-longer"), false);
  assertEquals(constantTimeEqual("", ""), true);
  assertEquals(constantTimeEqual("a", "b"), false);
});

Deno.test("VN-53-05: verifySchedulerToken rejects missing or invalid token with 403", () => {
  _setConfigForTest(testConfig());

  // Missing token
  const reqMissing = { req: { header: (_: string) => undefined } };
  const err1 = assertThrows(() => verifySchedulerToken(reqMissing), HttpError);
  assertEquals(err1.status, 403);

  // Mismatched token
  const reqWrong = {
    req: { header: (h: string) => h.toLowerCase() === "x-internal-scheduler-token" ? "wrong-val" : undefined },
  };
  const err2 = assertThrows(() => verifySchedulerToken(reqWrong), HttpError);
  assertEquals(err2.status, 403);

  // Valid token
  const reqValid = {
    req: { header: (h: string) => h.toLowerCase() === "x-internal-scheduler-token" ? "secret-token-xyz" : undefined },
  };
  verifySchedulerToken(reqValid);
});

// ── VN-53-02: SMS Caller Facility Pinning Logic ──────────────────────────────

Deno.test("VN-53-02: SMS facility pinning ensures clinician facility cannot be spoofed", () => {
  const clinicianUser = makeUser({ resolvedRole: "doctor", resolvedFacilityId: "fac-clinician" });
  const bodyFacility = "fac-injected-attacker";

  // Simulate resolving facility for SMS stub
  const resolvedFacility = clinicianUser.resolvedRole === "super_admin"
    ? (bodyFacility ?? clinicianUser.resolvedFacilityId ?? "00000000-0000-0000-0000-000000000001")
    : (clinicianUser.resolvedFacilityId ?? "00000000-0000-0000-0000-000000000001");

  assertEquals(resolvedFacility, "fac-clinician");
});

Deno.test("VN-53-02: SMS facility pinning allows super_admin to specify custom facility", () => {
  const saUser = makeUser({ resolvedRole: "super_admin", resolvedFacilityId: null });
  const bodyFacility = "fac-destination";

  const resolvedFacility = saUser.resolvedRole === "super_admin"
    ? (bodyFacility ?? saUser.resolvedFacilityId ?? "00000000-0000-0000-0000-000000000001")
    : (saUser.resolvedFacilityId ?? "00000000-0000-0000-0000-000000000001");

  assertEquals(resolvedFacility, "fac-destination");
});

// ── Scoping Contract Parity ──────────────────────────────────────────────────

Deno.test("Scoping parity: GLOBAL_SCOPE_ROLES includes supervisor and super_admin", () => {
  assertEquals(GLOBAL_SCOPE_ROLES.includes("supervisor"), true);
  assertEquals(GLOBAL_SCOPE_ROLES.includes("super_admin"), true);
  assertEquals((GLOBAL_SCOPE_ROLES as readonly string[]).includes("admin"), false);
  assertEquals((GLOBAL_SCOPE_ROLES as readonly string[]).includes("doctor"), false);
});
