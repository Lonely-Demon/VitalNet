-- Phase 16: LLM status / abstention / human-review-request fields
-- Idempotent — safe to run multiple times.
--
-- Adds the columns app/api/routes/cases.py writes on every case submission:
--   - low_confidence:          classifier abstention flag (ML C2)
--   - llm_status:               'generated' | 'fallback' (was the LLM briefing produced or degraded)
--   - needs_review:             low_confidence OR an explicit ASHA review request
--   - human_review_requested:   ASHA worker explicitly flagged this case for review
--   - human_review_reason:      free-text reason (required when human_review_requested)

BEGIN;

ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS low_confidence boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS llm_status text NOT NULL DEFAULT 'generated',
  ADD COLUMN IF NOT EXISTS needs_review boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS human_review_requested boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS human_review_reason text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'case_records_llm_status_check'
  ) THEN
    ALTER TABLE public.case_records
      ADD CONSTRAINT case_records_llm_status_check
      CHECK (llm_status IN ('generated', 'fallback'));
  END IF;
END $$;

-- Doctor dashboard filters/sorts on cases needing review.
CREATE INDEX IF NOT EXISTS idx_case_records_needs_review
  ON public.case_records (needs_review) WHERE needs_review = true;

COMMIT;
