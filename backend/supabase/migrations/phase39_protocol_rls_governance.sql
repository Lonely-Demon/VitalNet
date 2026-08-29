-- Phase 39: Protocol Questions RLS Governance (Supervisor global scope, PHC Admin local scope)
-- Restructures RLS policies on protocol_questions so:
-- 1. Supervisor role has global SELECT and UPDATE (curation) access across all facilities (matching supervisor no-facility model).
-- 2. PHC Administrator ('admin') role is scoped strictly to own facility_id for SELECT, INSERT, and UPDATE (curation).
-- 3. Doctor role can SELECT, INSERT, and UPDATE (curate) for own facility_id.
-- 4. ASHA Worker role can SELECT and INSERT for own facility_id.

DROP POLICY IF EXISTS protocol_questions_select_policy ON public.protocol_questions;
CREATE POLICY protocol_questions_select_policy
  ON public.protocol_questions
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND (p.role = 'supervisor' OR p.facility_id = protocol_questions.facility_id)
    )
  );

DROP POLICY IF EXISTS protocol_questions_insert_policy ON public.protocol_questions;
CREATE POLICY protocol_questions_insert_policy
  ON public.protocol_questions
  FOR INSERT TO authenticated
  WITH CHECK (
    asked_by = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND (p.role = 'supervisor' OR p.facility_id = protocol_questions.facility_id)
    )
  );

DROP POLICY IF EXISTS protocol_questions_update_policy ON public.protocol_questions;
CREATE POLICY protocol_questions_update_policy
  ON public.protocol_questions
  FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('doctor', 'supervisor', 'admin')
        AND (p.role = 'supervisor' OR p.facility_id = protocol_questions.facility_id)
    )
  );
