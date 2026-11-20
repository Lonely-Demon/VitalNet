"""
Facility-scope resolution — shared by aggregate-only dashboards
(supervisor team metrics, outbreak signals, analytics):
- `super_admin`: system-wide global administrator.
- `supervisor`: aggregate-only analytics role across facilities.
- `admin`: facility-scoped PHC administrator, pinned to own facility_id and cannot widen scope.
- staff roles (`doctor`, `asha_worker`): pinned to own facility_id.
"""
from fastapi import HTTPException

GLOBAL_SCOPE_ROLES = {"supervisor", "super_admin"}
GLOBAL_SCOPE_ROLE = "supervisor"  # backward compat


def resolve_facility_scope(
    role: str,
    own_facility_id: str | None,
    requested_facility_id: str | None,
) -> str | None:
    """
    Returns the facility_id to filter a query on, or None for system-wide
    (GLOBAL_SCOPE_ROLES only: supervisor and super_admin). A non-global role's
    own facility always wins — `requested_facility_id` is only honoured for global
    roles, so a facility-scoped account (such as PHC admin or clinician) can never
    widen their own scope by passing a different id. Raises HTTP 400 if a non-global
    role has no facility assigned (an account that was never fully provisioned).
    """
    if role in GLOBAL_SCOPE_ROLES:
        return requested_facility_id
    if not own_facility_id:
        raise HTTPException(status_code=400, detail="Account has no facility assigned")
    return own_facility_id
