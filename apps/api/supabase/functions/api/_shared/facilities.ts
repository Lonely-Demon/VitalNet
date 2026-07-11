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

/** Merges each facility with its open-case count (0 if absent from the RPC
 * result) and sorts least-loaded first — a suggestion, not an enforcement. */
export function mergeOpenCaseCounts(facilities: Facility[], openCounts: OpenCaseCountRow[]): FacilityWithLoad[] {
  const loadByFacility = new Map<string, number>();
  for (const row of openCounts) {
    if (row.facility_id) {
      loadByFacility.set(row.facility_id, row.open_count ?? 0);
    }
  }

  const merged = facilities.map((f) => ({ ...f, open_case_count: loadByFacility.get(f.id) ?? 0 }));
  merged.sort((a, b) => a.open_case_count - b.open_case_count);
  return merged;
}
