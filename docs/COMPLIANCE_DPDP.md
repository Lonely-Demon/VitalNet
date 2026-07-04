# VitalNet — Digital Personal Data Protection Act (DPDP), 2023 Mapping

VitalNet processes health data of rural patients in India, so India's
Digital Personal Data Protection Act, 2023 (DPDP Act) is the primary data
protection law it must map against. This document records how VitalNet's
existing architecture maps to the Act's obligations, what's implemented in
code today, and what remains a documented gap. It is a working compliance
map maintained by engineering, **not a legal opinion** — a real deployment
handling real patient data must have this reviewed by qualified counsel
before going live.

## Roles under the Act

- **Data Fiduciary** — the organisation operating VitalNet (determines
  purpose and means of processing). This is whoever deploys and operates a
  given VitalNet instance, not the codebase itself.
- **Data Processor** — any sub-processor engaged on the fiduciary's behalf.
  Today that's Supabase (database/auth/storage), Groq and Google (LLM
  briefing generation, Gemini as fallback — see `app/services/llm.py`), and
  a Web Push provider (browser vendors' push services). Each is a
  processing-location and sub-processor fact a fiduciary must disclose in
  its own privacy notice.
- **Data Principal** — the patient (or, for a minor, the patient's lawful
  guardian). Note the patient is usually *not* an authenticated VitalNet
  user — the ASHA worker and doctor are the authenticated users; the
  patient's data enters through them. This shapes several rights below.

## Lawful basis for processing

Processing patient vitals/symptoms/outcome data relies on **consent**
captured at the point of intake:

- `IntakeForm.consent_captured` / `consent_captured_at`
  (`app/models/schemas.py`) — the schema-level validator
  (`_require_consent`) makes submission **fail closed**: a case cannot be
  created at all without an affirmative consent flag and timestamp. This
  is enforced in Pydantic, not just the UI, so it can't be bypassed by a
  client that skips a screen.
- Consent is captured **from or on behalf of** the patient by the ASHA
  worker at the point of care — the ASHA worker is the one who must explain,
  in the patient's language, what is being collected and why, since the
  patient is not a system user reading a privacy policy screen themselves.
  This is an operational/training requirement on the deploying
  organisation, not something code can enforce.
- **Minors:** several supported symptom/vital profiles are explicitly
  paediatric (`clinical_features.py` age-banding, neonatal-fever safety-net
  rule). The Act requires **verifiable guardian consent** for a child's
  personal data. VitalNet does not currently have a separate
  "guardian consent" field distinct from `consent_captured` — this is a
  known gap (see "Gaps" below); today, consent capture is a single flag
  regardless of patient age, and the deploying organisation's ASHA-worker
  training/process must ensure a guardian is the one giving that consent
  when the patient is a minor.

## Data Principal rights — how each maps to current code

| Right (DPDP Act) | Current mechanism | Gap |
|---|---|---|
| Right to access a summary of personal data processed | Admin-only patient-record export endpoint (`POST /api/admin/patients/{client_id}/export`, see `docs/API_REFERENCE.md`) — returns every `case_records`/`case_outcomes`/`case_attachments`/`referrals` row tied to a `client_id` as one JSON bundle | Retrieval is admin-mediated (the patient has no login), consistent with the patient not being a system user; a real deployment needs an operational process for a patient/guardian to *request* this from the facility, which code cannot enforce |
| Right to correction and erasure | Erasure endpoint (`POST /api/admin/patients/{client_id}/erase`) anonymises identifying fields while preserving de-identified clinical/outcome data | **Tension, stated honestly:** clinical records are also subject to medical-record-retention expectations in most health systems; VitalNet's erasure endpoint anonymises (removes identifying fields) rather than hard-deletes clinical rows, so aggregate ML training and facility reporting integrity survive an erasure request. A deploying organisation must document this anonymisation-not-deletion choice in its own patient-facing notice — it is a policy decision this codebase cannot make on the organisation's behalf |
| Right to grievance redressal | None in-code today | Gap — requires a named Grievance Officer and a contact channel, which is an organisational fact, not a code fact. Document in the deploying organisation's privacy notice |
| Right to nominate (data access after death/incapacity) | Not implemented | Gap — same reasoning; this is a data-fiduciary-side operational commitment, not a per-request API |
| Withdrawal of consent | Not implemented as a standing revocable flag post-submission | Gap — today, `consent_captured` is captured once at intake; there is no "withdraw consent for future processing" flow. The erasure endpoint is the closest present mechanism |

## Data Fiduciary obligations — current implementation

- **Purpose limitation:** patient data collected via `IntakeForm` is used
  only for the clinical triage/referral/outcome workflow and, in
  de-identified/aggregate form, for model retraining
  (`scripts/retrain_from_outcomes.py`). No secondary commercial use exists
  in the codebase.
- **Data minimisation:** the intake schema is a bounded, purpose-specific
  set of clinical fields (`app/models/schemas.py`) — there is no
  collection of data unrelated to the triage/referral purpose (no
  behavioural tracking, no unrelated demographic profiling).
- **Security safeguards** (Section 8(5) of the Act): see `docs/SECURITY.md`
  for the full technical control set — encryption in transit, RLS,
  hybrid-JWT auth, rate limiting, PHI audit logging, security headers.
- **Breach notification** (Section 8(6)): the Act requires notifying the
  Data Protection Board and affected data principals in the event of a
  personal data breach. VitalNet's PHI audit log
  (`app/core/audit.py`, `phi_audit_log` table) is the forensic record a
  fiduciary would use to scope a breach's affected records and timeline —
  but **notification itself is an organisational/legal process, not
  something this codebase automates or can automate** (the Act does not
  fix a bright-line notification deadline the way, e.g., GDPR's 72 hours
  does, but "without delay" is the operative standard — confirm current
  guidance with counsel at the time of any real incident).
  `docs/INCIDENT_RESPONSE.md` documents the operational runbook this
  triggers.
- **Retention limitation:** `POST /api/admin/cases/purge-expired` implements
  a configurable retention window (`data_retention_days` setting) —
  anonymising records past that window the same way the erasure endpoint
  does. Like the existing unreviewed-EMERGENCY re-alert endpoint
  (`docs/DECISIONS.md`), it is meant to be hit on a schedule by an external
  scheduler (cron/Railway scheduled job/Supabase pg_cron/etc.), not run
  automatically inside this codebase; `data_retention_days = 0` (the
  default) disables it.
- **Data Protection Officer / significant data fiduciary obligations:**
  whether VitalNet's operator is a "Significant Data Fiduciary" under the
  Act (triggering DPO appointment, data protection impact assessments, and
  audits) depends on processing volume/sensitivity thresholds the
  government sets — an organisational determination outside this
  codebase's scope.

## Cross-border data transfer

Supabase project region and Groq/Gemini API processing location determine
where patient data actually resides/transits. The DPDP Act permits
cross-border transfer except to countries the Central Government
restricts by notification. **This codebase does not pin a data residency
region** — the deploying organisation must choose a Supabase project
region (and confirm Groq/Gemini's processing location) consistent with
its own data-residency obligations and disclose this in its privacy
notice. This is an infrastructure/deployment decision, not a code change.

## What's implemented vs. what's a documented organisational gap

**Implemented in this codebase:**
- Fail-closed consent capture at intake.
- Admin-mediated data-subject export and erasure/anonymisation endpoints
  (`docs/API_REFERENCE.md`), both PHI-audit-logged.
- A retention-policy script (age-gated anonymisation), operator-scheduled.
- The full technical security control set documented in `docs/SECURITY.md`.

**Explicitly not implementable by this codebase alone** (organisational,
legal, or infrastructure decisions a deploying entity must make):
- Grievance Officer designation and contact channel.
- Patient-facing privacy notice and consent-language localisation review
  (distinct from the app's own i18n scaffolding, `docs/DECISIONS.md` §10).
- Guardian-consent verification process for minors.
- Data-residency region selection and sub-processor disclosure.
- The determination of Significant Data Fiduciary status and any
  resulting DPO/DPIA/audit obligations.
- Formal legal review of this entire mapping before real deployment.
