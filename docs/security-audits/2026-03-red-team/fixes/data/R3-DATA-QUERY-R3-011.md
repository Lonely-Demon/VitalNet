# Fix Log: R3-DATA-QUERY-R3-011

**Unit ID:** R3-DATA-QUERY-R3-011
**Priority:** P2 (MEDIUM)
**Title:** No Index on case_records.submitted_by
**Status:** COMPLETED

## Finding Summary
`submitted_by` column is queried for user-specific case lists but lacks an index.

## Location
- `backend/app/api/routes/cases.py:230`
- `analytics_routes.py:65-67`

## Remediation Applied
Added index in `phase15_data_security_hardening.sql`:

```sql
CREATE INDEX IF NOT EXISTS idx_case_records_submitted_by
  ON public.case_records (submitted_by);
```

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 2)

## Risk Assessment
- **Before:** MEDIUM - Slow user-specific queries
- **After:** LOW - Index-backed lookups
