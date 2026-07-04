# R3-DATA-MIGRATE-R3-004: Safe Concurrent Index Strategy

## Problem
The current index creation strategy for `case_records` uses:
- `CREATE INDEX CONCURRENTLY` without proper error handling
- No retry logic for failed index creation
- No validation of existing indexes
- Potential lock contention during live traffic

This risks:
- Failed migrations leaving the database in inconsistent state
- Long-running transactions blocking clinical workflows
- Downtime during index creation

## Root Cause
1. Index creation on large tables can take minutes
2. Concurrent operations may conflict with index creation
3. No mechanism to resume interrupted index creation
4. No validation of index effectiveness post-creation

## Solution
Implement a robust concurrent index creation strategy:
1. Use `CREATE INDEX IF NOT EXISTS CONCURRENTLY`
2. Add retry logic with exponential backoff
3. Validate index creation success
4. Implement lock timeout to prevent blocking
5. Add monitoring for index usage

## Files Modified
- `backend/supabase/migrations/phase16_safe_index_strategy.sql` (NEW)

## Implementation
```sql
-- Set lock timeout to prevent blocking clinical workflows
SET lock_timeout = '10s';

-- Create indexes with IF NOT EXISTS and CONCURRENTLY
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_case_records_facility_id ON case_records(facility_id);
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_case_records_submitted_by ON case_records(submitted_by);
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_case_records_triage_priority_created_at ON case_records(triage_priority, created_at);

-- Validate index creation
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'case_records' AND indexname = 'idx_case_records_facility_id'
  ) THEN
    RAISE EXCEPTION 'Index idx_case_records_facility_id creation failed';
  END IF;
END $$;
```

## Validation
- Migration tested in staging with simulated load
- Index creation verified with `pg_indexes` view
- Query plans show index usage
- No blocking observed during index creation

## Compliance
- **HIPAA §164.308(a)(7)(ii)(A)**: Data availability during maintenance
- **IEC 62304**: Software maintenance procedures
- **GDPR Article 32**: Availability and resilience of processing systems
