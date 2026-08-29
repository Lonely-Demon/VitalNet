-- Phase 43: Prevent submitter mutation of clinical, vital, and identity columns
-- on case_records (VN-2026-08-C3-02).
--
-- Submitters (ASHA workers) can only update non-clinical fields on their own
-- records (such as soft-delete via deleted_at, or requesting human review).
-- Clinical modifications require doctor or admin role.

BEGIN;

CREATE OR REPLACE FUNCTION public.protect_case_records_clinical_columns()
RETURNS trigger AS $$
BEGIN
  -- Check: is the caller the original submitter and NOT a clinical role?
  IF auth.uid() = OLD.submitted_by
     AND NOT EXISTS (
       SELECT 1 FROM public.profiles p
       WHERE p.id = auth.uid()
         AND p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])
     )
  THEN
    IF NEW.patient_name IS DISTINCT FROM OLD.patient_name
       OR NEW.patient_age IS DISTINCT FROM OLD.patient_age
       OR NEW.patient_sex IS DISTINCT FROM OLD.patient_sex
       OR NEW.patient_location IS DISTINCT FROM OLD.patient_location
       OR NEW.patient_key IS DISTINCT FROM OLD.patient_key
       OR NEW.chief_complaint IS DISTINCT FROM OLD.chief_complaint
       OR NEW.complaint_duration IS DISTINCT FROM OLD.complaint_duration
       OR NEW.symptoms IS DISTINCT FROM OLD.symptoms
       OR NEW.observations IS DISTINCT FROM OLD.observations
       OR NEW.known_conditions IS DISTINCT FROM OLD.known_conditions
       OR NEW.current_medications IS DISTINCT FROM OLD.current_medications
       OR NEW.is_pregnant IS DISTINCT FROM OLD.is_pregnant
       OR NEW.contraindication_flags IS DISTINCT FROM OLD.contraindication_flags
       OR NEW.temperature IS DISTINCT FROM OLD.temperature
       OR NEW.heart_rate IS DISTINCT FROM OLD.heart_rate
       OR NEW.bp_systolic IS DISTINCT FROM OLD.bp_systolic
       OR NEW.bp_diastolic IS DISTINCT FROM OLD.bp_diastolic
       OR NEW.spo2 IS DISTINCT FROM OLD.spo2
       OR NEW.respiratory_rate IS DISTINCT FROM OLD.respiratory_rate
       OR NEW.triage_level IS DISTINCT FROM OLD.triage_level
       OR NEW.triage_confidence IS DISTINCT FROM OLD.triage_confidence
       OR NEW.triage_model_version IS DISTINCT FROM OLD.triage_model_version
       OR NEW.risk_driver IS DISTINCT FROM OLD.risk_driver
       OR NEW.low_confidence IS DISTINCT FROM OLD.low_confidence
       OR NEW.deterioration_alert IS DISTINCT FROM OLD.deterioration_alert
       OR NEW.deterioration_visit_count IS DISTINCT FROM OLD.deterioration_visit_count
       OR NEW.facility_id IS DISTINCT FROM OLD.facility_id
       OR NEW.client_id IS DISTINCT FROM OLD.client_id
       OR NEW.briefing IS DISTINCT FROM OLD.briefing
    THEN
      RAISE EXCEPTION 'Clinical and identity columns cannot be modified by the submitter';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_protect_case_records_clinical_columns ON public.case_records;
CREATE TRIGGER trg_protect_case_records_clinical_columns
  BEFORE UPDATE ON public.case_records
  FOR EACH ROW EXECUTE FUNCTION public.protect_case_records_clinical_columns();

COMMIT;
