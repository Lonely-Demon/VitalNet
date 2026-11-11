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

Deno.test("mergeOpenCaseCounts: sorts by 5-level priority (Tier -> District -> Capacity -> Open Cases -> Name)", () => {
  const fSubCentre = {
    id: "f1",
    name: "Alpha",
    type: "sub_centre",
    district: "District A",
    capacity_status: "available",
  };
  const fDistrictHosp = {
    id: "f2",
    name: "Beta",
    type: "district_hospital",
    district: "District B",
    capacity_status: "at_capacity",
  };
  const fChcMatchingDist = {
    id: "f3",
    name: "Gamma",
    type: "chc",
    district: "District A",
    capacity_status: "available",
  };
  const fChcOtherDist = { id: "f4", name: "Delta", type: "chc", district: "District B", capacity_status: "available" };

  // Tier rank wins: district_hospital (rank 0) > chc (rank 2) > sub_centre (rank 4)
  const resultTier = mergeOpenCaseCounts([fSubCentre, fDistrictHosp, fChcMatchingDist], [], "District A");
  assertEquals(resultTier.map((f) => f.id), ["f2", "f3", "f1"]);

  // Same tier (chc): matching district wins over other district
  const resultDist = mergeOpenCaseCounts([fChcOtherDist, fChcMatchingDist], [], "District A");
  assertEquals(resultDist.map((f) => f.id), ["f3", "f4"]);

  // Same tier and district: capacity status wins (available < near_capacity < at_capacity)
  const fChcNear = { id: "f5", name: "Epsilon", type: "chc", district: "District A", capacity_status: "near_capacity" };
  const resultCap = mergeOpenCaseCounts([fChcNear, fChcMatchingDist], [], "District A");
  assertEquals(resultCap.map((f) => f.id), ["f3", "f5"]);
});
