# Fix Log: R3-DATA-RLS-R3-001

**Unit ID:** R3-DATA-RLS-R3-001
**Priority:** P0 (CRITICAL)
**Title:** Admin Stats Endpoint Bypasses RLS via service_role Client
**Status:** ACCEPTED RISK (intentional design)

## Finding Summary
Admin stats endpoint uses service_role client which bypasses Row Level Security policies.

## Location
`backend/app/api/routes/admin_routes.py:216-217`

## Analysis
This is **intentional design**, not a vulnerability:

1. **Admin endpoints require cross-facility visibility** - Admin stats must aggregate data across all facilities
2. **Authentication gate exists** - The endpoint requires `super_admin` role via `require_role("super_admin")`
3. **service_role is appropriate** - Admin operations legitimately need RLS bypass for aggregate queries

## Mitigations in Place
1. `require_role("super_admin")` decorator on all admin endpoints
2. JWT validation ensures only authenticated super_admins access these routes
3. Audit logging added (ROOT-COMPLY-002) tracks all admin access
4. Network-level restrictions can limit admin API access in production

## Recommendation
No code change required. Document this as accepted design pattern:
> "Admin endpoints use service_role client for cross-facility aggregation. Access is gated by super_admin role requirement and logged for audit compliance."

## Files Modified
None (accepted risk)

## Risk Assessment
- **Severity:** Informational (accepted design pattern)
- **Residual Risk:** LOW - Multiple authentication layers protect access
