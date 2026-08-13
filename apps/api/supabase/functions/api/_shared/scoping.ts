// Ported verbatim from app/core/scoping.py — the facility-scope rule
// shared by every aggregate-only dashboard: 'admin' is the only global
// role, every other role is pinned to their own facility_id and cannot
// widen that scope via a query parameter.
import { HttpError } from "./database.ts";

export const GLOBAL_SCOPE_ROLE = "admin";

/**
 * Returns the facility_id to filter a query on, or null for system-wide
 * (GLOBAL_SCOPE_ROLE only). A non-global role's own facility always wins
 * — requestedFacilityId is only honoured for the global role, so a
 * facility-scoped account can never widen their own scope by passing a
 * different id. Throws HTTP 400 if a non-global role has no facility
 * assigned (an account that was never fully provisioned).
 */
export function resolveFacilityScope(
  role: string,
  ownFacilityId: string | null,
  requestedFacilityId: string | null,
): string | null {
  if (role === GLOBAL_SCOPE_ROLE) {
    return requestedFacilityId;
  }
  if (!ownFacilityId) {
    throw new HttpError(400, "Account has no facility assigned");
  }
  return ownFacilityId;
}
