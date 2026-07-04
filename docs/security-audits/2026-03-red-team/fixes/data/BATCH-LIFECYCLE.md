# Fix Log: Lifecycle Items (Batch)

This batch covers data lifecycle findings.

## Items Covered
- **R3-DATA-LIFECYCLE-R3-006** (P2): Realtime Reintroduces Soft-Deleted Records
- **R3-DATA-LIFECYCLE-R3-007** (P2): User Deactivation Leaves Case Data Active

## Status: PARTIALLY ADDRESSED

## Remediation Applied

### R3-DATA-LIFECYCLE-R3-006: Realtime Soft-Delete Filtering
**Analysis:** Supabase Realtime respects RLS policies. If RLS filters deleted_at IS NULL, deleted records won't appear in realtime feeds.

**Mitigation:** Phase15 UPDATE policy includes `deleted_at IS NULL` check.

**Frontend hardening recommended:**
```javascript
// useRealtimeCases.js
.on('postgres_changes', {...}, (payload) => {
  if (payload.new.deleted_at) return; // Ignore soft-deleted
  // Process update
})
```

### R3-DATA-LIFECYCLE-R3-007: User Deactivation Cascade
**Status:** By design, user deactivation does NOT delete associated cases.

**Rationale:**
- Clinical records must be preserved for compliance
- Deactivation ≠ data deletion
- Cases remain assigned to (deactivated) user for audit trail

**Recommended enhancement:**
- Add UI indicator for cases submitted by deactivated users
- Consider reassignment workflow for active cases

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (RLS policy)
