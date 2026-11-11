// Ported from backend/tests/test_scoping.py
import { assertEquals, assertThrows } from "@std/assert";
import { GLOBAL_SCOPE_ROLE, GLOBAL_SCOPE_ROLES, isGlobalScope, resolveFacilityScope, resolveScope } from "../_shared/scoping.ts";
import { HttpError } from "../_shared/database.ts";

Deno.test("GLOBAL_SCOPE_ROLES includes supervisor and super_admin", () => {
  assertEquals(GLOBAL_SCOPE_ROLE, "supervisor");
  assertEquals(GLOBAL_SCOPE_ROLES.includes("supervisor"), true);
  assertEquals(GLOBAL_SCOPE_ROLES.includes("super_admin"), true);
  assertEquals(isGlobalScope("supervisor"), true);
  assertEquals(isGlobalScope("super_admin"), true);
  assertEquals(isGlobalScope("admin"), false);
  assertEquals(isGlobalScope("doctor"), false);
});

Deno.test("supervisor defaults to system-wide (unscoped global access, is_global: true)", () => {
  assertEquals(resolveFacilityScope("supervisor", null, null), null);
  const scope = resolveScope("supervisor", null, null);
  assertEquals(scope.facilityId, null);
  assertEquals(scope.is_global, true);
});

Deno.test("supervisor can narrow to one facility", () => {
  assertEquals(resolveFacilityScope("supervisor", null, "fac-9"), "fac-9");
  const scope = resolveScope("supervisor", null, "fac-9");
  assertEquals(scope.facilityId, "fac-9");
  assertEquals(scope.is_global, false);
});

Deno.test("non-supervisor roles are scoped to own facility", () => {
  assertEquals(resolveFacilityScope("admin", "fac-1", null), "fac-1");
  assertEquals(resolveFacilityScope("doctor", "fac-1", null), "fac-1");
  assertEquals(resolveFacilityScope("asha_worker", "fac-1", null), "fac-1");
  const scope = resolveScope("admin", "fac-1", null);
  assertEquals(scope.facilityId, "fac-1");
  assertEquals(scope.is_global, false);
});

Deno.test("non-supervisor roles cannot widen scope via query param", () => {
  assertEquals(resolveFacilityScope("admin", "fac-1", "fac-2"), "fac-1");
  assertEquals(resolveFacilityScope("doctor", "fac-1", "fac-2"), "fac-1");
  assertEquals(resolveFacilityScope("asha_worker", "fac-1", "fac-2"), "fac-1");
});

Deno.test("non-supervisor roles without facility are rejected", () => {
  const errAdmin = assertThrows(() => resolveFacilityScope("admin", null, null), HttpError);
  assertEquals(errAdmin.status, 400);

  const errDoctor = assertThrows(() => resolveFacilityScope("doctor", null, null), HttpError);
  assertEquals(errDoctor.status, 400);

  const errAsha = assertThrows(() => resolveFacilityScope("asha_worker", null, null), HttpError);
  assertEquals(errAsha.status, 400);
});
