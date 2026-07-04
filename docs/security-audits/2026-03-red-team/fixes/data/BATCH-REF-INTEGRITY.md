# Fix Log: Reference Integrity Items (Batch)

This batch covers referential integrity findings.

## Items Covered
- **R3-DATA-REF-R3-001** (P1): Facility Delete No FK Child Action
- **R3-DATA-REF-R3-003** (P1): Cases Without Submitting User
- **R3-DATA-REF-R3-005** (P1): Facility Relationship Drift
- **R3-DATA-REF-R3-007** (P1): No facility_id Match Constraint
- **R3-DATA-REF-R3-008** (P1): create_user Assumes Profile Exists

## Status: PARTIALLY ADDRESSED

## Remediation Applied

### R3-DATA-REF-R3-001: Facility Delete FK Action
Added in phase15:
```sql
FOREIGN KEY (facility_id) REFERENCES facilities(id)
  ON UPDATE CASCADE
  ON DELETE RESTRICT
```
**RESTRICT** chosen to prevent orphaned cases.

### R3-DATA-REF-R3-003/005/007: Facility Consistency
Addressed via:
1. RLS policies enforce facility_id scoping
2. Application-level validation in cases.py
3. Foreign key ensures valid facility references

### R3-DATA-REF-R3-008: Profile Creation Race
**REQUIRES FURTHER WORK:**
- Trigger-based profile creation has race condition
- Recommendation: Use database transaction to atomically create auth.user + profile

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql`

## Remaining Work
- [ ] Implement atomic user+profile creation
- [ ] Add CHECK constraint for facility_id consistency
- [ ] Review trigger timing for profile creation
