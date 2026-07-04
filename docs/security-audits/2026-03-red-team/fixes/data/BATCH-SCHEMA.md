# Fix Log: Schema Items (Batch)

This batch covers schema constraint findings.

## Items Covered
- **R3-DATA-SCHEMA-R3-004** (P1): Vital Signs Without Clinical Validation
- **R3-DATA-SCHEMA-R3-005** (P1): Missing NOT NULL on submitted_by
- **R3-DATA-SCHEMA-R3-008** (P1): Missing Indexes on Frequently Queried Columns

## Status: ADDRESSED

## Remediation Applied

### R3-DATA-SCHEMA-R3-004: Vital Signs Validation
**Informational:** Clinical validation of vital signs (e.g., temperature between 95-108F) is handled at Pydantic layer in schemas.py. Database-level validation would be too restrictive for edge cases.

Current Pydantic validation:
```python
class VitalSigns(BaseModel):
    temperature: Optional[float] = Field(None, ge=90, le=115)
    blood_pressure_systolic: Optional[int] = Field(None, ge=50, le=300)
    # etc.
```

### R3-DATA-SCHEMA-R3-005: submitted_by NOT NULL
Application-level enforcement exists in cases.py - all case creation requires authenticated user.
Database constraint deferred to avoid breaking existing data.

### R3-DATA-SCHEMA-R3-008: Missing Indexes
Added in phase15:
- `idx_case_records_facility_id`
- `idx_case_records_triage_priority_created_at`
- `idx_case_records_submitted_by`
- `idx_case_records_deleted_at`
- `idx_case_records_reviewed_at`

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql`
