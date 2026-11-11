// Ported from referral_routes.py::list_active_facilities' merge/sort step.
// Pure function so the "least-loaded first" ordering is testable without a
// live database.

export interface Facility {
  id: string;
  name: string;
  type: string | null;
  district: string | null;
  capacity_status: string | null;
}

export interface FacilityWithLoad extends Facility {
  open_case_count: number;
}

export interface OpenCaseCountRow {
  facility_id: string | null;
  open_count: number | null;
}

export const TIER_RANK: Record<string, number> = {
  district_hospital: 0,
  sdh: 1,
  sub_district_hospital: 1,
  chc: 2,
  phc: 3,
  sub_centre: 4,
};

export const CAPACITY_RANK: Record<string, number> = {
  available: 0,
  limited: 1,
  full: 2,
};

/** Merges each facility with its open-case count (0 if absent from the RPC
 * result) and sorts by tier hierarchy, district proximity, capacity status rank,
 * open case count, then name (BUG-28). */
export function mergeOpenCaseCounts(
  facilities: Facility[],
  openCounts: OpenCaseCountRow[],
  callerDistrict?: string | null,
): FacilityWithLoad[] {
  const loadByFacility = new Map<string, number>();
  for (const row of openCounts) {
    if (row.facility_id) {
      loadByFacility.set(row.facility_id, row.open_count ?? 0);
    }
  }

  const merged = facilities.map((f) => ({ ...f, open_case_count: loadByFacility.get(f.id) ?? 0 }));
  merged.sort((a, b) => {
    // 1. Tier hierarchy
    const tierA = TIER_RANK[(a.type ?? "").toLowerCase()] ?? 99;
    const tierB = TIER_RANK[(b.type ?? "").toLowerCase()] ?? 99;
    if (tierA !== tierB) return tierA - tierB;

    // 2. District proximity
    const distA = callerDistrict && a.district === callerDistrict ? 0 : 1;
    const distB = callerDistrict && b.district === callerDistrict ? 0 : 1;
    if (distA !== distB) return distA - distB;

    // 3. Capacity status rank
    const rankA = CAPACITY_RANK[a.capacity_status ?? ""] ?? 1;
    const rankB = CAPACITY_RANK[b.capacity_status ?? ""] ?? 1;
    if (rankA !== rankB) return rankA - rankB;

    // 4. Open case count ascending
    if (a.open_case_count !== b.open_case_count) return a.open_case_count - b.open_case_count;

    // 5. Name alphabetically
    return (a.name || "").localeCompare(b.name || "");
  });
  return merged;
}
