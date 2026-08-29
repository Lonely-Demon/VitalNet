-- Phase 45: Real immutability triggers for case_reviews (VN-2026-08-C3-04).
--
-- Replaces the no-op CHECK (true) intent marker with BEFORE UPDATE and
-- BEFORE DELETE triggers that strictly forbid mutation or deletion.

BEGIN;

CREATE OR REPLACE FUNCTION public.prevent_case_review_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'case_reviews is append-only: updates and deletes are prohibited';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_case_reviews_no_update ON public.case_reviews;
CREATE TRIGGER trg_case_reviews_no_update
  BEFORE UPDATE ON public.case_reviews
  FOR EACH ROW EXECUTE FUNCTION public.prevent_case_review_mutation();

DROP TRIGGER IF EXISTS trg_case_reviews_no_delete ON public.case_reviews;
CREATE TRIGGER trg_case_reviews_no_delete
  BEFORE DELETE ON public.case_reviews
  FOR EACH ROW EXECUTE FUNCTION public.prevent_case_review_mutation();

COMMIT;
