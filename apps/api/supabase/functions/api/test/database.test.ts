import { assertEquals, assertThrows } from "@std/assert";
import { extractBearerToken, HttpError } from "../_shared/database.ts";

const WELL_FORMED = "aaa.bbb.ccc";

Deno.test("extractBearerToken: valid header returns the token", () => {
  assertEquals(extractBearerToken(`Bearer ${WELL_FORMED}`), WELL_FORMED);
});

Deno.test("extractBearerToken: case-insensitive scheme", () => {
  assertEquals(extractBearerToken(`bearer ${WELL_FORMED}`), WELL_FORMED);
});

Deno.test("extractBearerToken: missing header throws 401", () => {
  const err = assertThrows(() => extractBearerToken(null), HttpError);
  assertEquals(err.status, 401);
});

Deno.test("extractBearerToken: empty header throws 401", () => {
  assertThrows(() => extractBearerToken(""), HttpError);
});

Deno.test("extractBearerToken: wrong scheme throws 401", () => {
  assertThrows(() => extractBearerToken(`Basic ${WELL_FORMED}`), HttpError);
});

Deno.test("extractBearerToken: not a 3-part JWT throws 401", () => {
  assertThrows(() => extractBearerToken("Bearer not-a-jwt"), HttpError);
});

Deno.test("extractBearerToken: extra whitespace is tolerated", () => {
  assertEquals(extractBearerToken(`  Bearer   ${WELL_FORMED}  `), WELL_FORMED);
});
