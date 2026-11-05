// _shared/scoping.test.ts — Unit tests for scoping.ts
import { assertEquals, assertThrows } from "@std/assert";
import { GLOBAL_SCOPE_ROLE, isGlobalScope, resolveFacilityScope, resolveScope } from "./scoping.ts";
import { HttpError } from "./database.ts";

Deno.test("_shared/scoping: GLOBAL_SCOPE_ROLE is supervisor", () => {
  assertEquals(GLOBAL_SCOPE_ROLE, "supervisor");
  assertEquals(isGlobalScope("supervisor"), true);
  assertEquals(isGlobalScope("admin"), false);
  assertEquals(isGlobalScope("doctor"), false);
});

Deno.test("_shared/scoping: supervisor receives unscoped global access (is_global: true)", () => {
  assertEquals(resolveFacilityScope("supervisor", null, null), null);
  const scope = resolveScope("supervisor", null, null);
  assertEquals(scope.facilityId, null);
  assertEquals(scope.is_global, true);
});

Deno.test("_shared/scoping: supervisor can narrow to one facility", () => {
  assertEquals(resolveFacilityScope("supervisor", null, "fac-9"), "fac-9");
  const scope = resolveScope("supervisor", null, "fac-9");
  assertEquals(scope.facilityId, "fac-9");
  assertEquals(scope.is_global, false);
});

Deno.test("_shared/scoping: non-supervisor roles are scoped to own facility", () => {
  assertEquals(resolveFacilityScope("admin", "fac-1", null), "fac-1");
  assertEquals(resolveFacilityScope("doctor", "fac-1", null), "fac-1");
  assertEquals(resolveFacilityScope("asha_worker", "fac-1", null), "fac-1");
  const scope = resolveScope("admin", "fac-1", null);
  assertEquals(scope.facilityId, "fac-1");
  assertEquals(scope.is_global, false);
});

Deno.test("_shared/scoping: non-supervisor roles without facility are rejected", () => {
  const errAdmin = assertThrows(() => resolveFacilityScope("admin", null, null), HttpError);
  assertEquals(errAdmin.status, 400);

  const errDoctor = assertThrows(() => resolveFacilityScope("doctor", null, null), HttpError);
  assertEquals(errDoctor.status, 400);
});
