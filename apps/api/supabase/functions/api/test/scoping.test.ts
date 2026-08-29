// Ported from backend/tests/test_scoping.py
import { assertEquals, assertThrows } from "@std/assert";
import { resolveFacilityScope } from "../_shared/scoping.ts";
import { HttpError } from "../_shared/database.ts";

Deno.test("non-admin role is scoped to own facility", () => {
  assertEquals(resolveFacilityScope("supervisor", "fac-1", null), "fac-1");
  assertEquals(resolveFacilityScope("doctor", "fac-1", null), "fac-1");
});

Deno.test("non-admin role cannot widen scope via query param", () => {
  assertEquals(resolveFacilityScope("supervisor", "fac-1", "fac-2"), "fac-1");
  assertEquals(resolveFacilityScope("doctor", "fac-1", "fac-2"), "fac-1");
});

Deno.test("non-admin role without facility is rejected", () => {
  const err = assertThrows(() => resolveFacilityScope("supervisor", null, null), HttpError);
  assertEquals(err.status, 400);
});

Deno.test("admin defaults to system-wide", () => {
  assertEquals(resolveFacilityScope("admin", null, null), null);
});

Deno.test("admin can narrow to one facility", () => {
  assertEquals(resolveFacilityScope("admin", null, "fac-9"), "fac-9");
});
