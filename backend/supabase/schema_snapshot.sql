-- VitalNet live-schema baseline snapshot — public schema, captured directly
-- from the production Supabase project via pg_catalog introspection
-- (format_type/pg_get_expr/pg_get_constraintdef/pg_get_indexdef — the same
-- functions pg_dump itself uses), NOT hand-written or guessed.
--
-- Represents the schema state AS OF phase27 (i.e. immediately before
-- phase28_security_definer_fns.sql). backend/supabase/migrations/ has no
-- tracked migration for anything before phase10 — the foundational schema
-- (this file) was created directly against the project before migration
-- tracking started, and is captured here for the first time. See
-- docs/DECISIONS.md for the full story of how this was obtained and why
-- SNAPSHOT_BASELINE_PHASE (below) matters.
--
-- CI (.github/workflows/ci.yml's db-schema-drift job) loads this file into
-- a fresh Postgres container, then applies every tracked migration with a
-- phase number greater than SNAPSHOT_BASELINE_PHASE, in order — verifying
-- new migrations actually apply cleanly against a known-good ancestor
-- state. It does NOT need to be regenerated when a new migration is added;
-- migrations layer on top of it indefinitely. Only bump
-- SNAPSHOT_BASELINE_PHASE (and regenerate this file) if you want to
-- periodically fold migrations into the baseline to keep CI fast, or if
-- you discover further untracked live drift that needs recapturing.
--
-- Known gap: two functions referenced by profiles_select_policy_hardened
-- below — get_user_role(uuid) and get_user_facility(uuid) — exist on the
-- live project but appear in NO tracked migration anywhere in this repo.
-- They're stubbed for CI in the db-schema-drift job (not defined here,
-- since this file should only contain what's genuinely tracked/verified).
-- Recommended follow-up: pull their real definitions via
-- pg_get_functiondef() and add a proper migration for them.

-- SNAPSHOT_BASELINE_PHASE=27

CREATE TABLE public.case_attachments (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  case_id uuid NOT NULL,
  uploaded_by uuid NOT NULL,
  storage_path text NOT NULL,
  content_type text NOT NULL,
  size_bytes integer NOT NULL,
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE TABLE public.case_outcomes (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  case_id uuid NOT NULL,
  recorded_by uuid NOT NULL,
  actual_severity text NOT NULL,
  patient_disposition text NOT NULL,
  outcome_notes text,
  recorded_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE TABLE public.case_records (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  client_id uuid NOT NULL,
  submitted_by uuid,
  facility_id uuid,
  patient_age integer,
  patient_sex text,
  patient_location text,
  bp_systolic integer,
  bp_diastolic integer,
  spo2 integer,
  heart_rate integer,
  temperature numeric(4,1),
  chief_complaint text NOT NULL,
  complaint_duration text,
  symptoms text[],
  observations text,
  known_conditions text,
  current_medications text,
  triage_level text NOT NULL,
  triage_confidence numeric(5,4),
  risk_driver text,
  briefing jsonb,
  llm_model_used text,
  reviewed_by uuid,
  reviewed_at timestamp with time zone,
  doctor_notes text,
  created_offline boolean DEFAULT false,
  client_submitted_at timestamp with time zone,
  synced_at timestamp with time zone,
  deleted_at timestamp with time zone,
  deleted_by uuid,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  patient_name text,
  triage_priority integer GENERATED ALWAYS AS (
CASE triage_level
    WHEN 'EMERGENCY'::text THEN 0
    WHEN 'URGENT'::text THEN 1
    WHEN 'ROUTINE'::text THEN 2
    ELSE 3
END) STORED,
  consent_captured boolean DEFAULT false NOT NULL,
  consent_captured_at timestamp with time zone,
  low_confidence boolean DEFAULT false NOT NULL,
  llm_status text DEFAULT 'generated'::text NOT NULL,
  needs_review boolean DEFAULT false NOT NULL,
  human_review_requested boolean DEFAULT false NOT NULL,
  human_review_reason text,
  triage_model_version text,
  overridden_triage text,
  override_reason text,
  overridden_by uuid,
  overridden_at timestamp with time zone,
  last_escalated_at timestamp with time zone,
  contraindication_flags jsonb DEFAULT '[]'::jsonb NOT NULL,
  patient_key text,
  deterioration_alert boolean DEFAULT false NOT NULL,
  deterioration_visit_count integer,
  is_pregnant boolean
);
CREATE TABLE public.case_referrals (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  case_id uuid NOT NULL,
  from_facility uuid NOT NULL,
  to_facility uuid NOT NULL,
  referred_by uuid NOT NULL,
  status text DEFAULT 'INITIATED'::text NOT NULL,
  urgency text DEFAULT 'ROUTINE'::text NOT NULL,
  reason text NOT NULL,
  outcome_note text,
  created_at timestamp with time zone DEFAULT now() NOT NULL,
  updated_at timestamp with time zone DEFAULT now() NOT NULL,
  resolved_at timestamp with time zone
);
CREATE TABLE public.case_reviews (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  case_id uuid NOT NULL,
  reviewer_id uuid NOT NULL,
  reviewed_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
  note text
);
CREATE TABLE public.facilities (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  name text NOT NULL,
  type text DEFAULT 'PHC'::text NOT NULL,
  address text,
  district text,
  state text DEFAULT 'Tamil Nadu'::text,
  pincode text,
  phone text,
  is_active boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  capacity_status text DEFAULT 'available'::text NOT NULL,
  capacity_updated_at timestamp with time zone
);
CREATE TABLE public.phi_audit_log (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  event_type text NOT NULL,
  user_id uuid,
  user_role text,
  resource_type text NOT NULL,
  resource_id text,
  facility_id uuid,
  ip_address inet,
  details jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE TABLE public.profiles (
  id uuid NOT NULL,
  full_name text DEFAULT ''::text NOT NULL,
  role text DEFAULT 'asha_worker'::text NOT NULL,
  facility_id uuid,
  asha_id text,
  phone text,
  is_active boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now()
);
CREATE TABLE public.protocol_questions (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  asked_by uuid NOT NULL,
  facility_id uuid NOT NULL,
  question_text text NOT NULL,
  language text DEFAULT 'en'::text NOT NULL,
  llm_answer_text text,
  llm_grounded boolean DEFAULT false NOT NULL,
  status text DEFAULT 'pending_curation'::text NOT NULL,
  curator_answer_text text,
  curated_by uuid,
  curated_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE TABLE public.push_subscriptions (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  user_id uuid NOT NULL,
  facility_id uuid,
  endpoint text NOT NULL,
  p256dh_key text NOT NULL,
  auth_key text NOT NULL,
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE TABLE public.referrals (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  case_id uuid NOT NULL,
  referred_by uuid NOT NULL,
  referring_facility_id uuid NOT NULL,
  receiving_facility_id uuid NOT NULL,
  reason text NOT NULL,
  urgency text NOT NULL,
  status text DEFAULT 'pending'::text NOT NULL,
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.case_attachments ADD CONSTRAINT case_attachments_pkey PRIMARY KEY (id);
ALTER TABLE public.case_outcomes ADD CONSTRAINT case_outcomes_pkey PRIMARY KEY (id);
ALTER TABLE public.case_records ADD CONSTRAINT case_records_pkey PRIMARY KEY (id);
ALTER TABLE public.case_referrals ADD CONSTRAINT case_referrals_pkey PRIMARY KEY (id);
ALTER TABLE public.case_reviews ADD CONSTRAINT case_reviews_pkey PRIMARY KEY (id);
ALTER TABLE public.facilities ADD CONSTRAINT facilities_pkey PRIMARY KEY (id);
ALTER TABLE public.phi_audit_log ADD CONSTRAINT phi_audit_log_pkey PRIMARY KEY (id);
ALTER TABLE public.profiles ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);
ALTER TABLE public.protocol_questions ADD CONSTRAINT protocol_questions_pkey PRIMARY KEY (id);
ALTER TABLE public.push_subscriptions ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);
ALTER TABLE public.referrals ADD CONSTRAINT referrals_pkey PRIMARY KEY (id);

ALTER TABLE public.case_records ADD CONSTRAINT case_records_client_id_key UNIQUE (client_id);
ALTER TABLE public.case_records ADD CONSTRAINT case_records_client_id_unique UNIQUE (client_id);
ALTER TABLE public.profiles ADD CONSTRAINT profiles_asha_id_key UNIQUE (asha_id);
ALTER TABLE public.push_subscriptions ADD CONSTRAINT push_subscriptions_endpoint_key UNIQUE (endpoint);

ALTER TABLE public.case_attachments ADD CONSTRAINT case_attachments_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES profiles(id) ON DELETE RESTRICT;
ALTER TABLE public.case_attachments ADD CONSTRAINT case_attachments_case_id_fkey FOREIGN KEY (case_id) REFERENCES case_records(id) ON DELETE CASCADE;
ALTER TABLE public.case_outcomes ADD CONSTRAINT case_outcomes_case_id_fkey FOREIGN KEY (case_id) REFERENCES case_records(id) ON DELETE CASCADE;
ALTER TABLE public.case_outcomes ADD CONSTRAINT case_outcomes_recorded_by_fkey FOREIGN KEY (recorded_by) REFERENCES profiles(id) ON DELETE RESTRICT;
ALTER TABLE public.case_records ADD CONSTRAINT case_records_overridden_by_fkey FOREIGN KEY (overridden_by) REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE public.case_records ADD CONSTRAINT case_records_submitted_by_fkey FOREIGN KEY (submitted_by) REFERENCES profiles(id);
ALTER TABLE public.case_records ADD CONSTRAINT case_records_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES facilities(id);
ALTER TABLE public.case_records ADD CONSTRAINT case_records_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES profiles(id);
ALTER TABLE public.case_records ADD CONSTRAINT case_records_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES profiles(id);
ALTER TABLE public.case_referrals ADD CONSTRAINT case_referrals_case_id_fkey FOREIGN KEY (case_id) REFERENCES case_records(id) ON DELETE RESTRICT;
ALTER TABLE public.case_referrals ADD CONSTRAINT case_referrals_from_facility_fkey FOREIGN KEY (from_facility) REFERENCES facilities(id);
ALTER TABLE public.case_referrals ADD CONSTRAINT case_referrals_to_facility_fkey FOREIGN KEY (to_facility) REFERENCES facilities(id);
ALTER TABLE public.case_reviews ADD CONSTRAINT case_reviews_case_id_fkey FOREIGN KEY (case_id) REFERENCES case_records(id) ON DELETE CASCADE;
ALTER TABLE public.case_reviews ADD CONSTRAINT case_reviews_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES profiles(id) ON DELETE RESTRICT;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES facilities(id);
ALTER TABLE public.profiles ADD CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE public.protocol_questions ADD CONSTRAINT protocol_questions_asked_by_fkey FOREIGN KEY (asked_by) REFERENCES profiles(id) ON DELETE RESTRICT;
ALTER TABLE public.protocol_questions ADD CONSTRAINT protocol_questions_curated_by_fkey FOREIGN KEY (curated_by) REFERENCES profiles(id) ON DELETE SET NULL;
ALTER TABLE public.protocol_questions ADD CONSTRAINT protocol_questions_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE RESTRICT;
ALTER TABLE public.push_subscriptions ADD CONSTRAINT push_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES profiles(id) ON DELETE CASCADE;
ALTER TABLE public.push_subscriptions ADD CONSTRAINT push_subscriptions_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE CASCADE;
ALTER TABLE public.referrals ADD CONSTRAINT referrals_referred_by_fkey FOREIGN KEY (referred_by) REFERENCES profiles(id) ON DELETE RESTRICT;
ALTER TABLE public.referrals ADD CONSTRAINT referrals_receiving_facility_id_fkey FOREIGN KEY (receiving_facility_id) REFERENCES facilities(id) ON DELETE RESTRICT;
ALTER TABLE public.referrals ADD CONSTRAINT referrals_referring_facility_id_fkey FOREIGN KEY (referring_facility_id) REFERENCES facilities(id) ON DELETE RESTRICT;
ALTER TABLE public.referrals ADD CONSTRAINT referrals_case_id_fkey FOREIGN KEY (case_id) REFERENCES case_records(id) ON DELETE CASCADE;

ALTER TABLE public.case_attachments ADD CONSTRAINT case_attachments_size_bytes_check CHECK ((size_bytes > 0));
ALTER TABLE public.case_outcomes ADD CONSTRAINT case_outcomes_actual_severity_check CHECK ((actual_severity = ANY (ARRAY['ROUTINE'::text, 'URGENT'::text, 'EMERGENCY'::text])));
ALTER TABLE public.case_outcomes ADD CONSTRAINT case_outcomes_patient_disposition_check CHECK ((patient_disposition = ANY (ARRAY['treated_discharged'::text, 'admitted'::text, 'referred_higher_facility'::text, 'deceased'::text, 'unknown'::text])));
ALTER TABLE public.case_records ADD CONSTRAINT case_records_patient_sex_check CHECK ((patient_sex = ANY (ARRAY['male'::text, 'female'::text, 'other'::text])));
ALTER TABLE public.case_records ADD CONSTRAINT case_records_llm_status_check CHECK ((llm_status = ANY (ARRAY['generated'::text, 'fallback'::text])));
ALTER TABLE public.case_records ADD CONSTRAINT case_records_triage_priority_map_check CHECK ((((triage_level = 'EMERGENCY'::text) AND (triage_priority = 0)) OR ((triage_level = 'URGENT'::text) AND (triage_priority = 1)) OR ((triage_level = 'ROUTINE'::text) AND (triage_priority = 2)) OR (triage_priority IS NULL)));
ALTER TABLE public.case_records ADD CONSTRAINT case_records_overridden_triage_check CHECK (((overridden_triage IS NULL) OR (overridden_triage = ANY (ARRAY['ROUTINE'::text, 'URGENT'::text, 'EMERGENCY'::text]))));
ALTER TABLE public.case_records ADD CONSTRAINT case_records_triage_level_check CHECK ((triage_level = ANY (ARRAY['ROUTINE'::text, 'URGENT'::text, 'EMERGENCY'::text])));
ALTER TABLE public.case_records ADD CONSTRAINT case_records_patient_key_format_check CHECK (((patient_key IS NULL) OR (patient_key ~ '^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$'::text)));
ALTER TABLE public.case_referrals ADD CONSTRAINT different_facilities CHECK ((from_facility <> to_facility));
ALTER TABLE public.case_referrals ADD CONSTRAINT case_referrals_urgency_check CHECK ((urgency = ANY (ARRAY['EMERGENCY'::text, 'URGENT'::text, 'ROUTINE'::text])));
ALTER TABLE public.case_referrals ADD CONSTRAINT case_referrals_status_check CHECK ((status = ANY (ARRAY['INITIATED'::text, 'ACKNOWLEDGED'::text, 'IN_REVIEW'::text, 'RESOLVED'::text, 'DECLINED'::text])));
ALTER TABLE public.case_reviews ADD CONSTRAINT case_reviews_immutable CHECK (true);
ALTER TABLE public.facilities ADD CONSTRAINT facilities_capacity_status_check CHECK ((capacity_status = ANY (ARRAY['available'::text, 'limited'::text, 'full'::text])));
ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check CHECK ((role = ANY (ARRAY['asha_worker'::text, 'doctor'::text, 'supervisor'::text, 'admin'::text])));
ALTER TABLE public.protocol_questions ADD CONSTRAINT protocol_questions_language_check CHECK ((language = ANY (ARRAY['en'::text, 'hi'::text, 'ta'::text])));
ALTER TABLE public.protocol_questions ADD CONSTRAINT protocol_questions_question_text_check CHECK (((char_length(question_text) >= 1) AND (char_length(question_text) <= 500)));
ALTER TABLE public.protocol_questions ADD CONSTRAINT protocol_questions_status_check CHECK ((status = ANY (ARRAY['answered'::text, 'pending_curation'::text, 'curated'::text])));
ALTER TABLE public.referrals ADD CONSTRAINT referrals_urgency_check CHECK ((urgency = ANY (ARRAY['ROUTINE'::text, 'URGENT'::text, 'EMERGENCY'::text])));
ALTER TABLE public.referrals ADD CONSTRAINT referrals_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'acknowledged'::text, 'patient_arrived'::text, 'completed'::text, 'cancelled'::text])));
ALTER TABLE public.referrals ADD CONSTRAINT referrals_distinct_facilities CHECK ((referring_facility_id <> receiving_facility_id));

CREATE INDEX idx_case_attachments_case_id ON public.case_attachments USING btree (case_id);
CREATE INDEX idx_case_outcomes_case_id ON public.case_outcomes USING btree (case_id);
CREATE INDEX idx_case_outcomes_recorded_by ON public.case_outcomes USING btree (recorded_by);
CREATE INDEX idx_case_records_patient_key ON public.case_records USING btree (patient_key) WHERE (patient_key IS NOT NULL);
CREATE UNIQUE INDEX idx_case_records_client_id_unique ON public.case_records USING btree (client_id);
CREATE INDEX idx_case_records_deleted_at ON public.case_records USING btree (deleted_at) WHERE (deleted_at IS NOT NULL);
CREATE INDEX idx_case_records_triage_priority_created_at ON public.case_records USING btree (triage_priority, created_at DESC);
CREATE INDEX idx_case_records_facility ON public.case_records USING btree (facility_id, created_at DESC) WHERE (deleted_at IS NULL);
CREATE INDEX idx_case_records_triage_level ON public.case_records USING btree (triage_level) WHERE (deleted_at IS NULL);
CREATE INDEX idx_case_records_triage_sort ON public.case_records USING btree (triage_priority, created_at DESC) WHERE (deleted_at IS NULL);
CREATE INDEX idx_case_records_submitted_by ON public.case_records USING btree (submitted_by, deleted_at);
CREATE INDEX idx_case_records_active_created ON public.case_records USING btree (deleted_at, created_at DESC) WHERE (deleted_at IS NULL);
CREATE INDEX idx_case_records_needs_review ON public.case_records USING btree (needs_review) WHERE (needs_review = true);
CREATE INDEX idx_case_records_facility_id ON public.case_records USING btree (facility_id);
CREATE INDEX idx_case_records_reviewed_at ON public.case_records USING btree (reviewed_at) WHERE (reviewed_at IS NOT NULL);
CREATE INDEX idx_referrals_status ON public.case_referrals USING btree (status);
CREATE INDEX idx_referrals_to_facility ON public.case_referrals USING btree (to_facility);
CREATE INDEX idx_referrals_case_id ON public.case_referrals USING btree (case_id);
CREATE INDEX idx_referrals_from_facility ON public.case_referrals USING btree (from_facility);
CREATE INDEX idx_case_reviews_case_id ON public.case_reviews USING btree (case_id);
CREATE INDEX idx_case_reviews_reviewer_id ON public.case_reviews USING btree (reviewer_id);
CREATE INDEX idx_phi_audit_log_user_id ON public.phi_audit_log USING btree (user_id);
CREATE INDEX idx_phi_audit_log_resource ON public.phi_audit_log USING btree (resource_type, resource_id);
CREATE INDEX idx_phi_audit_log_created_at ON public.phi_audit_log USING btree (created_at DESC);
CREATE INDEX idx_protocol_questions_status ON public.protocol_questions USING btree (status);
CREATE INDEX idx_protocol_questions_facility_id ON public.protocol_questions USING btree (facility_id);
CREATE INDEX idx_push_subscriptions_user_id ON public.push_subscriptions USING btree (user_id);
CREATE INDEX idx_push_subscriptions_facility_id ON public.push_subscriptions USING btree (facility_id);
CREATE INDEX idx_referrals_referring_facility ON public.referrals USING btree (referring_facility_id);
CREATE INDEX idx_referrals_receiving_facility ON public.referrals USING btree (receiving_facility_id);

ALTER TABLE public.case_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.facilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.phi_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.protocol_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.referrals ENABLE ROW LEVEL SECURITY;

CREATE POLICY case_attachments_select_policy ON public.case_attachments AS PERMISSIVE FOR SELECT TO public USING ((EXISTS ( SELECT 1
   FROM (case_records cr
     JOIN profiles p ON ((p.id = auth.uid())))
  WHERE ((cr.id = case_attachments.case_id) AND ((p.role = 'admin'::text) OR (p.facility_id = cr.facility_id) OR (cr.submitted_by = auth.uid()))))));
CREATE POLICY case_attachments_insert_policy ON public.case_attachments AS PERMISSIVE FOR INSERT TO public WITH CHECK (((uploaded_by = auth.uid()) AND (EXISTS ( SELECT 1
   FROM (case_records cr
     JOIN profiles p ON ((p.id = auth.uid())))
  WHERE ((cr.id = case_attachments.case_id) AND ((p.role = 'admin'::text) OR (p.facility_id = cr.facility_id) OR (cr.submitted_by = auth.uid())))))));
CREATE POLICY case_outcomes_select_policy ON public.case_outcomes AS PERMISSIVE FOR SELECT TO public USING (((recorded_by = auth.uid()) OR (EXISTS ( SELECT 1
   FROM (case_records cr
     JOIN profiles p ON ((p.id = auth.uid())))
  WHERE ((cr.id = case_outcomes.case_id) AND ((p.role = 'admin'::text) OR (p.facility_id = cr.facility_id)))))));
CREATE POLICY case_outcomes_insert_policy ON public.case_outcomes AS PERMISSIVE FOR INSERT TO public WITH CHECK (((recorded_by = auth.uid()) AND (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['doctor'::text, 'admin'::text])))))));
CREATE POLICY doctor_update ON public.case_records AS PERMISSIVE FOR UPDATE TO public USING ((((auth.jwt() -> 'user_metadata'::text) ->> 'role'::text) = ANY (ARRAY['doctor'::text, 'admin'::text])));
CREATE POLICY asha_select_own ON public.case_records AS PERMISSIVE FOR SELECT TO public USING (((deleted_at IS NULL) AND ((submitted_by = auth.uid()) OR (((auth.jwt() -> 'user_metadata'::text) ->> 'role'::text) = ANY (ARRAY['doctor'::text, 'admin'::text])))));
CREATE POLICY authenticated_insert ON public.case_records AS PERMISSIVE FOR INSERT TO public WITH CHECK ((submitted_by = auth.uid()));
CREATE POLICY case_records_delete_policy ON public.case_records AS PERMISSIVE FOR DELETE TO public USING (((auth.uid() = submitted_by) OR (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])))))));
CREATE POLICY case_records_update_policy ON public.case_records AS PERMISSIVE FOR UPDATE TO public USING (((deleted_at IS NULL) AND ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])) AND ((p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])) OR (p.facility_id = case_records.facility_id))))) OR (submitted_by = auth.uid())))) WITH CHECK (((submitted_by = submitted_by) AND ((reviewed_by IS NULL) OR (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text]))))))));
CREATE POLICY "Doctors can create referrals from their facility" ON public.case_referrals AS PERMISSIVE FOR INSERT TO public WITH CHECK (((from_facility = (((auth.jwt() -> 'user_metadata'::text) ->> 'facility_id'::text))::uuid) AND (((auth.jwt() -> 'user_metadata'::text) ->> 'role'::text) = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text]))));
CREATE POLICY "Receiving facility can update referrals" ON public.case_referrals AS PERMISSIVE FOR UPDATE TO public USING (((to_facility = (((auth.jwt() -> 'user_metadata'::text) ->> 'facility_id'::text))::uuid) OR (((auth.jwt() -> 'user_metadata'::text) ->> 'role'::text) = ANY (ARRAY['admin'::text, 'super_admin'::text])))) WITH CHECK (((to_facility = (((auth.jwt() -> 'user_metadata'::text) ->> 'facility_id'::text))::uuid) OR (((auth.jwt() -> 'user_metadata'::text) ->> 'role'::text) = ANY (ARRAY['admin'::text, 'super_admin'::text]))));
CREATE POLICY "Users can view referrals for their facility" ON public.case_referrals AS PERMISSIVE FOR SELECT TO public USING (((from_facility = (((auth.jwt() -> 'user_metadata'::text) ->> 'facility_id'::text))::uuid) OR (to_facility = (((auth.jwt() -> 'user_metadata'::text) ->> 'facility_id'::text))::uuid) OR (((auth.jwt() -> 'user_metadata'::text) ->> 'role'::text) = ANY (ARRAY['admin'::text, 'super_admin'::text]))));
CREATE POLICY case_reviews_insert_policy ON public.case_reviews AS PERMISSIVE FOR INSERT TO public WITH CHECK (((reviewer_id = auth.uid()) AND (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text, 'super_admin'::text])))))));
CREATE POLICY case_reviews_select_policy ON public.case_reviews AS PERMISSIVE FOR SELECT TO public USING (((reviewer_id = auth.uid()) OR (EXISTS ( SELECT 1
   FROM (case_records cr
     JOIN profiles p ON ((p.id = auth.uid())))
  WHERE ((cr.id = case_reviews.case_id) AND ((p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])) OR (p.facility_id = cr.facility_id)))))));
CREATE POLICY facilities_select_policy ON public.facilities AS PERMISSIVE FOR SELECT TO public USING ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND ((p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])) OR (p.facility_id = facilities.id))))));
CREATE POLICY facilities_update_policy ON public.facilities AS PERMISSIVE FOR UPDATE TO public USING ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND ((p.role = ANY (ARRAY['admin'::text, 'super_admin'::text])) OR (p.facility_id = facilities.id))))));
CREATE POLICY facilities_public_read ON public.facilities AS PERMISSIVE FOR SELECT TO public USING (true);
CREATE POLICY phi_audit_log_insert_only ON public.phi_audit_log AS PERMISSIVE FOR INSERT TO public WITH CHECK (true);
CREATE POLICY phi_audit_log_select_admin ON public.phi_audit_log AS PERMISSIVE FOR SELECT TO public USING ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['admin'::text, 'super_admin'::text]))))));
CREATE POLICY profiles_select_policy_hardened ON public.profiles AS PERMISSIVE FOR SELECT TO public USING (((id = auth.uid()) OR (get_user_role(auth.uid()) = ANY (ARRAY['admin'::text, 'super_admin'::text])) OR ((get_user_role(auth.uid()) = ANY (ARRAY['doctor'::text, 'facility_admin'::text])) AND (get_user_facility(auth.uid()) = facility_id))));
CREATE POLICY profile_select ON public.profiles AS PERMISSIVE FOR SELECT TO public USING (((id = auth.uid()) OR (((auth.jwt() -> 'user_metadata'::text) ->> 'role'::text) = 'admin'::text)));
CREATE POLICY protocol_questions_update_policy ON public.protocol_questions AS PERMISSIVE FOR UPDATE TO public USING ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['doctor'::text, 'supervisor'::text, 'admin'::text])) AND ((p.role = 'admin'::text) OR (p.facility_id = protocol_questions.facility_id))))));
CREATE POLICY protocol_questions_select_policy ON public.protocol_questions AS PERMISSIVE FOR SELECT TO public USING ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND ((p.role = 'admin'::text) OR (p.facility_id = protocol_questions.facility_id))))));
CREATE POLICY protocol_questions_insert_policy ON public.protocol_questions AS PERMISSIVE FOR INSERT TO public WITH CHECK (((asked_by = auth.uid()) AND (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.facility_id = protocol_questions.facility_id))))));
CREATE POLICY push_subscriptions_insert_own ON public.push_subscriptions AS PERMISSIVE FOR INSERT TO public WITH CHECK ((user_id = auth.uid()));
CREATE POLICY push_subscriptions_select_own ON public.push_subscriptions AS PERMISSIVE FOR SELECT TO public USING ((user_id = auth.uid()));
CREATE POLICY push_subscriptions_delete_own ON public.push_subscriptions AS PERMISSIVE FOR DELETE TO public USING ((user_id = auth.uid()));
CREATE POLICY referrals_select_policy ON public.referrals AS PERMISSIVE FOR SELECT TO public USING ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND ((p.role = 'admin'::text) OR (p.facility_id = ANY (ARRAY[referrals.referring_facility_id, referrals.receiving_facility_id])))))));
CREATE POLICY referrals_insert_policy ON public.referrals AS PERMISSIVE FOR INSERT TO public WITH CHECK (((referred_by = auth.uid()) AND (EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND (p.role = ANY (ARRAY['doctor'::text, 'admin'::text])) AND ((p.role = 'admin'::text) OR (p.facility_id = referrals.referring_facility_id)))))));
CREATE POLICY referrals_update_policy ON public.referrals AS PERMISSIVE FOR UPDATE TO public USING ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = auth.uid()) AND ((p.role = 'admin'::text) OR ((p.role = 'doctor'::text) AND (p.facility_id = referrals.receiving_facility_id)))))));
