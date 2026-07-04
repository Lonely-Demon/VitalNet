-- Phase 20: Patient photo attachments — SCHEMA SCAFFOLDING ONLY
-- (FEATURES_ROADMAP §3.2), per explicit user decision. `storage_path` is a
-- generic string so this schema works with whichever storage backend gets
-- chosen later (Supabase Storage vs external) — no live upload endpoint is
-- wired to it yet; that needs the storage/consent/retention policy decision
-- the roadmap itself flags as still open.
-- Idempotent — safe to run multiple times.

BEGIN;

CREATE TABLE IF NOT EXISTS public.case_attachments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES public.case_records(id) ON DELETE CASCADE,
  uploaded_by uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  storage_path text NOT NULL,
  content_type text NOT NULL,
  size_bytes integer NOT NULL CHECK (size_bytes > 0),
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_case_attachments_case_id ON public.case_attachments(case_id);

ALTER TABLE public.case_attachments ENABLE ROW LEVEL SECURITY;

-- Visibility mirrors case_outcomes_select_policy: admin globally, a doctor
-- scoped to the case's facility, or the ASHA worker who submitted the case.
DROP POLICY IF EXISTS case_attachments_select_policy ON public.case_attachments;
CREATE POLICY case_attachments_select_policy
  ON public.case_attachments
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.case_records cr
      JOIN public.profiles p ON p.id = auth.uid()
      WHERE cr.id = case_attachments.case_id
        AND (p.role = 'admin' OR p.facility_id = cr.facility_id OR cr.submitted_by = auth.uid())
    )
  );

-- Same access boundary applies to inserts — whoever can see the case can
-- attach a photo to it.
DROP POLICY IF EXISTS case_attachments_insert_policy ON public.case_attachments;
CREATE POLICY case_attachments_insert_policy
  ON public.case_attachments
  FOR INSERT
  WITH CHECK (
    uploaded_by = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.case_records cr
      JOIN public.profiles p ON p.id = auth.uid()
      WHERE cr.id = case_id
        AND (p.role = 'admin' OR p.facility_id = cr.facility_id OR cr.submitted_by = auth.uid())
    )
  );

-- No UPDATE/DELETE policies — immutable by omission, matching case_outcomes.

COMMIT;
