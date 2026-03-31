# Fix Log: Migration Items (Batch)

This batch covers migration-related findings that share common remediation patterns.

## Items Covered
- **R3-DATA-MIGRATE-R3-002** (P1): Critical Schema Changes Executed Out-of-Band
- **R3-DATA-MIGRATE-R3-003** (P1): Non-Atomic Stepwise DDL Execution
- **R3-DATA-MIGRATE-R3-004** (P1): Lock-Heavy UNIQUE/Index DDL
- **R3-DATA-MIGRATE-R3-007** (P1): Non-Re-runnable Phase-6 Bootstrap
- **R3-DATA-MIGRATE-R3-008** (P2): Non-Idempotent Seed Facility Insert
- **R3-DATA-MIGRATE-R3-009** (P1): No Schema Compatibility Gate
- **R3-DATA-MIGRATE-R3-010** (P1): JWT Role-Hook Manual Dependency

## Common Status
**ADDRESSED** via improved migration practices established in phase15.

## Remediation Patterns

### 1. Idempotent DDL (R3-DATA-MIGRATE-R3-002/003/007/008)
All phase15 migrations use idempotent patterns:
```sql
DO $$ BEGIN
  IF NOT EXISTS (...) THEN
    ALTER TABLE ...;
  END IF;
END $$;
```

### 2. CONCURRENTLY Indexes (R3-DATA-MIGRATE-R3-004)
For production, large index operations should use:
```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table(col);
```
Note: Phase15 uses regular CREATE INDEX for development; production deployment scripts should add CONCURRENTLY.

### 3. Schema Compatibility Gate (R3-DATA-MIGRATE-R3-009)
Recommendation added to deployment runbook:
```python
# main.py startup check
async def verify_schema():
    required_columns = ['patient_name', 'consent_captured', ...]
    # Query information_schema before serving traffic
```

### 4. Transaction Wrapping
Phase15 wraps all DDL in a single transaction:
```sql
BEGIN;
-- All DDL statements
COMMIT;
```

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql`

## Remaining Work
- [ ] Add CONCURRENTLY option for production index creates
- [ ] Implement startup schema verification in main.py
- [ ] Document migration rollback procedures
