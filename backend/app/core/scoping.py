"""
Facility-scope resolution — shared by the aggregate-only dashboards
(supervisor team metrics, outbreak signals) that follow the same rule
already established in analytics_routes.py: `admin` is the only global-scope
role, every other role is pinned to their own facility_id and cannot widen
that scope via a query parameter.
"""
from fastapi import HTTPException

GLOBAL_SCOPE_ROLE = "admin"


def resolve_facility_scope(
    role: str,
    own_facility_id: str | None,
    requested_facility_id: str | None,
) -> str | None:
    """
    Returns the facility_id to filter a query on, or None for system-wide
    (GLOBAL_SCOPE_ROLE only). A non-global role's own facility always wins —
    `requested_facility_id` is only honoured for the global role, so a
    facility-scoped account can never widen their own scope by passing a
    different id. Raises HTTP 400 if a non-global role has no facility
    assigned (an account that was never fully provisioned).
    """
    if role == GLOBAL_SCOPE_ROLE:
        return requested_facility_id
    if not own_facility_id:
        raise HTTPException(status_code=400, detail="Account has no facility assigned")
    return own_facility_id
