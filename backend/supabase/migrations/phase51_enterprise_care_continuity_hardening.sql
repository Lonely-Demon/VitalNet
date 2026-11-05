-- backend/supabase/migrations/phase51_enterprise_care_continuity_hardening.sql
-- Phase 51: Closed-Loop Referral Follow-Up & Cross-Transport SMS Stub Promotion
-- Sequenced after phase50_audit_rls_rbac_and_indexes.sql.
-- Preserves [CRITICAL-3]'s strict JSONB submitter allowlist.

BEGIN;

-- 1. Add post-referral ASHA follow-up tracking columns & SMS-stub promotion flag
ALTER TABLE public.case_records
  ADD COLUMN IF NOT EXISTS follow_up_required boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS follow_up_due_at timestamptz,
  ADD COLUMN IF NOT EXISTS follow_up_completed_at timestamptz,
  ADD COLUMN IF NOT EXISTS is_sms_stub boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_case_records_followup_due
  ON public.case_records (submitted_by, follow_up_due_at)
  WHERE follow_up_required = true AND follow_up_completed_at IS NULL AND deleted_at IS NULL;

-- 2. Extend protect_case_records_clinical_columns() from phase50 ([CRITICAL-3]):
--    Preserves the strict JSONB allowlist (blocking forged overrides, needs_review
--    tampering, and all clinical/vital mutations) while permitting:
--    (a) One-time promotion from an offline SMS stub (OLD.is_sms_stub = true -> NEW.is_sms_stub = false)
--        by the original submitter when the full HTTPS outbox record syncs.
--    (b) Submitter completion of post-referral follow-up (`follow_up_completed_at`).
CREATE OR REPLACE FUNCTION public.protect_case_records_clinical_columns()
RETURNS trigger AS $$
DECLARE
  v_allowed_submitter_cols text[] := ARRAY[
    'deleted_at',
    'human_review_requested',
    'human_review_reason',
    'follow_up_completed_at',
    'updated_at'
  ];
BEGIN
  -- Allow one-time state promotion from an offline SMS stub to the full synced record
  IF OLD.is_sms_stub IS TRUE AND NEW.is_sms_stub IS FALSE AND auth.uid() = OLD.submitted_by THEN
    RETURN NEW;
  END IF;

  IF auth.uid() = OLD.submitted_by
     AND NOT EXISTS (
       SELECT 1 FROM public.profiles p
       WHERE p.id = auth.uid()
         AND p.is_active = true
         AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
     )
  THEN
    IF (to_jsonb(NEW) - v_allowed_submitter_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_submitter_cols) THEN
      RAISE EXCEPTION 'Clinical, triage, override, and identity columns cannot be modified by the submitter';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. SECURITY DEFINER RPC: fn_mark_referral_followup_due
--    Called by the receiving facility's doctor when a referral transitions to 'completed'.
--    Schedules a 48-hour post-discharge follow-up check on the originating case_records row.
CREATE OR REPLACE FUNCTION public.fn_mark_referral_followup_due(
  p_case_id uuid,
  p_referral_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_role text;
  v_own_facility uuid;
  v_receiving_facility uuid;
BEGIN
  SELECT p.role, p.facility_id INTO v_role, v_own_facility
  FROM public.profiles p WHERE p.id = auth.uid() AND p.is_active;

  IF v_role NOT IN ('doctor', 'admin') THEN
    RAISE EXCEPTION 'insufficient_privilege' USING ERRCODE = '42501';
  END IF;

  SELECT r.receiving_facility_id INTO v_receiving_facility
  FROM public.referrals r
  WHERE r.id = p_referral_id AND r.case_id = p_case_id;

  IF v_receiving_facility IS NULL THEN
    RAISE EXCEPTION 'referral not found' USING ERRCODE = 'P0002';
  END IF;

  IF v_role <> 'admin' AND v_own_facility IS DISTINCT FROM v_receiving_facility THEN
    RAISE EXCEPTION 'only receiving facility can trigger post-referral follow-up' USING ERRCODE = '42501';
  END IF;

  UPDATE public.case_records
  SET follow_up_required = true,
      follow_up_due_at = now() + interval '48 hours'
  WHERE id = p_case_id AND deleted_at IS NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_mark_referral_followup_due(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fn_mark_referral_followup_due(uuid, uuid) TO authenticated;

COMMIT;
