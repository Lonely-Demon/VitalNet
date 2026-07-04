# Fix Log: R3-DATA-QUERY-R3-006

**Unit ID:** R3-DATA-QUERY-R3-006
**Priority:** P1 (HIGH)
**Title:** Missing Index on case_records.facility_id
**Status:** COMPLETED

## Finding Summary
`facility_id` column is frequently queried (facility-scoped queries) but lacks an index, causing full table scans.

## Location
Inferred from `analytics_routes.py:29`, `cases.py:156`

## Remediation Applied
Added index in `phase15_data_security_hardening.sql`:

```sql
CREATE INDEX IF NOT EXISTS idx_case_records_facility_id
  ON public.case_records (facility_id);
```

## Query Patterns Optimized
- `SELECT * FROM case_records WHERE facility_id = ?`
- RLS policy lookups using facility_id
- Analytics queries filtered by facility

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 2)

## Risk Assessment
- **Before:** HIGH - Full table scans on facility queries
- **After:** LOW - Index-backed lookups

## Verification
```sql
EXPLAIN SELECT * FROM case_records WHERE facility_id = '<uuid>';
-- Should show: Index Scan using idx_case_records_facility_id
```
