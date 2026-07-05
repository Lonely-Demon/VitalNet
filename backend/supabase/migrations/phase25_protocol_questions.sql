-- Phase 25: Protocol/guideline lookup assistant (docs/DECISIONS.md §27)
-- Idempotent — safe to run multiple times.
--
-- Carries NO patient identifiers or PHI — questions are general protocol/
-- guideline queries, not patient-specific (enforced by the LLM system
-- prompt in app/services/llm.py, which refuses patient-specific questions).
-- This is why the SELECT policy below is facility-wide for every role,
-- unlike case_records: sharing this data facility-wide is safe and is the
-- whole point of a shared, growing FAQ.

BEGIN;

CREATE TABLE IF NOT EXISTS public.protocol_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asked_by uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  facility_id uuid NOT NULL REFERENCES public.facilities(id) ON DELETE RESTRICT,
  question_text text NOT NULL CHECK (char_length(question_text) BETWEEN 1 AND 500),
  language text NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'hi', 'ta')),
  llm_answer_text text,
  llm_grounded boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'pending_curation'
    CHECK (status IN ('answered', 'pending_curation', 'curated')),
  curator_answer_text text,
  curated_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  curated_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_protocol_questions_facility_id ON public.protocol_questions(facility_id);
CREATE INDEX IF NOT EXISTS idx_protocol_questions_status ON public.protocol_questions(status);

ALTER TABLE public.protocol_questions ENABLE ROW LEVEL SECURITY;

-- Visible facility-wide to EVERY role at that facility (asha_worker
-- included — no PHI here, so a shared FAQ is safe and is the whole point),
-- or globally to admin.
DROP POLICY IF EXISTS protocol_questions_select_policy ON public.protocol_questions;
CREATE POLICY protocol_questions_select_policy
  ON public.protocol_questions
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND (p.role = 'admin' OR p.facility_id = protocol_questions.facility_id)
    )
  );

-- Any authenticated user with a facility can ask a question tied to their
-- own facility_id (mirrors the app-level check in protocol_routes.py).
DROP POLICY IF EXISTS protocol_questions_insert_policy ON public.protocol_questions;
CREATE POLICY protocol_questions_insert_policy
  ON public.protocol_questions
  FOR INSERT
  WITH CHECK (
    asked_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid() AND p.facility_id = protocol_questions.facility_id
    )
  );

-- Curation (setting curator_answer_text/curated_by/curated_at/status) is
-- limited to supervisor/doctor/admin at that facility, or admin globally —
-- ASHA workers ask, they don't curate.
DROP POLICY IF EXISTS protocol_questions_update_policy ON public.protocol_questions;
CREATE POLICY protocol_questions_update_policy
  ON public.protocol_questions
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('doctor', 'supervisor', 'admin')
        AND (p.role = 'admin' OR p.facility_id = protocol_questions.facility_id)
    )
  );

COMMIT;
