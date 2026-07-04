# R3-DATA-SCHEMA-R3-004: Vital Sign Validation at Database Level

## Problem
Vital sign validation (ranges, nullability) is currently enforced only at the API layer via Pydantic schemas. This leaves the database vulnerable to:
- Direct table inserts bypassing API validation
- Schema migrations that might relax constraints
- Inconsistent validation between API and database

## Root Cause
The `case_records` table lacks robust constraints for vital signs:
- `bp_systolic`, `bp_diastolic`: No range constraints
- `spo2`: No range constraints (should be 50-100%)
- `heart_rate`: No range constraints
- `temperature`: No range constraints
- Missing NOT NULL constraints for required vital signs

## Solution
Add comprehensive database-level constraints that mirror the Pydantic validation:
- CHECK constraints for valid ranges
- NOT NULL constraints for required fields
- Align with existing Pydantic validation in `IntakeForm` schema

## Files Modified
- `backend/supabase/migrations/phase16_vital_sign_constraints.sql` (NEW)
- `backend/app/models/schemas.py`

## Constraints Added
```sql
ALTER TABLE case_records
ADD CONSTRAINT valid_bp_systolic CHECK (bp_systolic BETWEEN 30 AND 300),
ADD CONSTRAINT valid_bp_diastolic CHECK (bp_diastolic BETWEEN 10 AND 200),
ADD CONSTRAINT valid_spo2 CHECK (spo2 BETWEEN 50 AND 100),
ADD CONSTRAINT valid_heart_rate CHECK (heart_rate BETWEEN 10 AND 250),
ADD CONSTRAINT valid_temperature CHECK (temperature BETWEEN 25.0 AND 45.0);
```

## Validation
- Direct SQL inserts with invalid values are rejected
- API validation remains unchanged (defense in depth)
- Migration tested in staging with sample data

## Compliance
- **HIPAA**: Ensures data integrity for clinical decision support
- **GDPR**: Prevents invalid data that could lead to incorrect patient care
- **IEC 62304**: Aligns with software safety class B requirements
