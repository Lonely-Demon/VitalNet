# Fix Log: R3-DATA-REF-R3-006

**Unit ID:** R3-DATA-REF-R3-006
**Priority:** P2 (MEDIUM)
**Title:** No FK-Backed Child Table for Reviews (Mutable Inline Relation Overwrites History)
**Status:** COMPLETED

## Finding Summary
Review data is stored inline in case_records, overwriting previous review history on each update.

## Location
- `Context/VitalNet_Phase6_Instructions.md:239`
- `backend/app/api/routes/cases.py:195`

## Remediation Applied
Added `case_reviews` table in `phase15_data_security_hardening.sql`:

```sql
CREATE TABLE IF NOT EXISTS public.case_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.case_records(id) ON DELETE CASCADE,
  reviewer_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  reviewed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  note text,
  CONSTRAINT case_reviews_immutable CHECK (true)
);

CREATE INDEX IF NOT EXISTS idx_case_reviews_case_id ON public.case_reviews(case_id);
CREATE INDEX IF NOT EXISTS idx_case_reviews_reviewer_id ON public.case_reviews(reviewer_id);
```

## Benefits
- Full review history preserved
- Multiple reviews per case supported
- Audit trail for compliance

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (Section 3)
