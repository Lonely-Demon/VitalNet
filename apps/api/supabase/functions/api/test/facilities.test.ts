import { assertEquals } from "@std/assert";
import { type Facility, mergeOpenCaseCounts, type OpenCaseCountRow } from "../_shared/facilities.ts";

function facility(id: string, name: string): Facility {
  return { id, name, type: "PHC", district: "Test District", capacity_status: "available" };
}

Deno.test("mergeOpenCaseCounts: facility with no matching count defaults to 0", () => {
  const result = mergeOpenCaseCounts([facility("f1", "Facility A")], []);
  assertEquals(result, [{ ...facility("f1", "Facility A"), open_case_count: 0 }]);
});

Deno.test("mergeOpenCaseCounts: attaches the matching count", () => {
  const counts: OpenCaseCountRow[] = [{ facility_id: "f1", open_count: 5 }];
  const result = mergeOpenCaseCounts([facility("f1", "Facility A")], counts);
  assertEquals(result[0]?.open_case_count, 5);
});

Deno.test("mergeOpenCaseCounts: sorts least-loaded first", () => {
  const facilities = [facility("f1", "Busy"), facility("f2", "Quiet"), facility("f3", "Medium")];
  const counts: OpenCaseCountRow[] = [
    { facility_id: "f1", open_count: 10 },
    { facility_id: "f2", open_count: 0 },
    { facility_id: "f3", open_count: 3 },
  ];
  const result = mergeOpenCaseCounts(facilities, counts);
  assertEquals(result.map((f) => f.id), ["f2", "f3", "f1"]);
});

Deno.test("mergeOpenCaseCounts: null facility_id rows are ignored", () => {
  const counts: OpenCaseCountRow[] = [{ facility_id: null, open_count: 99 }];
  const result = mergeOpenCaseCounts([facility("f1", "Facility A")], counts);
  assertEquals(result[0]?.open_case_count, 0);
});
