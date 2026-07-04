# Fix Log: R3-DATA-REF-R3-002

**Unit ID:** R3-DATA-REF-R3-002
**Priority:** P0 (CRITICAL)
**Title:** User-Deletion Cascade Chain Is Internally Inconsistent
**Status:** PARTIALLY ADDRESSED (requires operational decision)

## Finding Summary
User deletion cascade behavior is inconsistent across tables - some use CASCADE, others RESTRICT or no action, leading to potential orphan records or failed deletions.

## Location
- `Context/VitalNet_Phase6_Instructions.md:169,211,239,248`

## Remediation Applied
Phase 15 migration establishes consistent FK relationships:
1. `case_records.facility_id` → `facilities.id` with `ON DELETE RESTRICT`
2. `case_reviews.reviewer_id` → `profiles.id` with `ON DELETE RESTRICT`
3. `case_reviews.case_id` → `case_records.id` with `ON DELETE CASCADE`

## Design Decision
**RESTRICT** was chosen over CASCADE for user-linked records because:
- PHI records should not be silently deleted when a user is removed
- Compliance requires audit trail preservation
- Deactivation (not deletion) is the preferred user removal path

## Remaining Action Items
1. Update user deactivation flow to handle cases appropriately
2. Document operational procedure for user data handling
3. Consider adding a scheduled job to archive orphaned records

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql`

## Risk Assessment
- **Before:** HIGH - Inconsistent cascade behavior could cause data loss or integrity errors
- **After:** MEDIUM - Consistent RESTRICT prevents data loss; operational procedure needed

## Testing Notes
Attempt to delete a user with case records - should be blocked with FK violation.
