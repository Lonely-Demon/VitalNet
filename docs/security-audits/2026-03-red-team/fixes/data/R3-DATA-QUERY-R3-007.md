# Fix Log: R3-DATA-QUERY-R3-007

**Unit ID:** R3-DATA-QUERY-R3-007
**Priority:** P1 (HIGH)
**Title:** Missing Composite Index on (triage_priority, created_at)
**Status:** COMPLETED

## Finding Summary
Queries that sort by triage priority and created_at (common dashboard pattern) lack a composite index.

## Location
`backend/app/api/routes/cases.py:157-159`

## Remediation Applied
Added composite index in `phase15_data_security_hardening.sql`:

```sql
CREATE INDEX IF NOT EXISTS idx_case_records_triage_priority_created_at
  ON public.case_records (triage_priority, created_at DESC);
```

## Query Patterns Optimized
- `SELECT * FROM case_records ORDER BY triage_priority, created_at DESC`
- Dashboard case lists sorted by urgency
- Analytics queries for time-series by priority

## Index Design
- **Column order:** `(triage_priority, created_at DESC)` matches query pattern
- **DESC on created_at:** Optimizes for "most recent first" queries

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 2)

## Risk Assessment
- **Before:** HIGH - Expensive sorts on large tables
- **After:** LOW - Index-backed sorted scans
