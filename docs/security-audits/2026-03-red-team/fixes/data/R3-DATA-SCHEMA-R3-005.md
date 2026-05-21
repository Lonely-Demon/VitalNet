# R3-DATA-SCHEMA-R3-005: Submitted By Audit Integrity

## Problem
The `submitted_by` field in `case_records` can be:
- NULL (missing submitter identity)
- Forged (API allows client to specify any value)
- Inconsistent with the actual submitting user's JWT

This breaks audit integrity and prevents accurate tracing of case submissions.

## Root Cause
1. The API currently trusts the client-provided `submitted_by` value
2. No database constraint prevents NULL values
3. No server-side validation ensures `submitted_by` matches the authenticated user

## Solution
Implement server-authoritative submitter identity:
1. **Database**: Add NOT NULL constraint and FK to `auth.users`
2. **Backend**: Remove client-provided `submitted_by` from API input
3. **Backend**: Set `submitted_by` server-side from JWT `sub` claim
4. **Backend**: Add audit logging for submission events

## Files Modified
- `backend/supabase/migrations/phase16_submitted_by_integrity.sql` (NEW)
- `backend/app/api/routes/cases.py`
- `backend/app/models/schemas.py`

## Evidence
- `backend/app/api/routes/cases.py` now writes `submitted_by` from `user["sub"]` server-side.

## Changes Made
### Database
```sql
ALTER TABLE case_records
ALTER COLUMN submitted_by SET NOT NULL,
ADD CONSTRAINT fk_submitted_by FOREIGN KEY (submitted_by) REFERENCES auth.users(id) ON DELETE RESTRICT;
```

### Backend
- Removed `submitted_by` from `IntakeForm` schema
- Set `submitted_by` server-side from `user["sub"]`
- Added audit logging for case creation

## Validation
- API rejects cases with client-provided `submitted_by`
- Database rejects NULL or invalid user IDs
- Audit logs show correct submitting user
- Existing cases with NULL `submitted_by` are migrated

## Compliance
- **HIPAA §164.312(b)**: Audit controls for PHI access
- **HIPAA §164.502(g)**: Accurate attribution of actions
- **GDPR Article 30**: Maintain records of processing activities
