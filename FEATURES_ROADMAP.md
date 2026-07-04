# VitalNet — Feature Roadmap

A prioritized backlog of proposed features, each with the reasoning for
why it matters specifically for VitalNet's use case (rural Indian
healthcare, offline-first, ASHA/doctor/admin roles), and implementation-
ready specs detailed enough to execute without re-deriving the design.

Prioritization framework: **Tier 1** = fixes a real gap in patient safety,
data integrity, or operational trust, and is feasible without a major new
subsystem. **Tier 2** = clear value, larger effort or a new external
dependency. **Tier 3** = high value but speculative/large scope — needs a
product decision before implementation starts.

---

## Tier 1 — Do first

### 1.1 Version-controlled Supabase migrations + RLS policies — ✅ DONE

**Status**: Implemented in the round-3 reconciliation. Migrations now live
in `backend/supabase/migrations/` (`phase10_realtime_setup.sql`,
`phase15_data_security_hardening.sql`, `phase16_llm_review_fields.sql`) —
idempotent, hand-written SQL covering schema constraints, indexes, the
`case_reviews` and `phi_audit_log` tables, consent-capture columns, and the
actual RLS policies (documented in `CODEBASE_MAP.md` §5). Steps 1-2 and 5-8
below (Supabase CLI linking, `supabase db pull` reconciliation workflow, CI
lint job) are not yet done — the migrations are hand-written and applied
manually via the SQL editor rather than through the CLI push/pull workflow.
That remains a reasonable follow-up but the core structural gap (schema/RLS
unauditable from the repo) is closed.

**Why (original)**: The audit that produced this roadmap found that VitalNet's entire
database schema and every Row Level Security policy exist only inside the
live Supabase project — `database/` contains exactly one SQL file
(Realtime setup). This means: no code review ever happens on an RLS policy
change, there is no way to reproduce the database from git history, no way
to diff what changed between deployments, and no way to spin up a second
environment (staging) with a guaranteed-identical security posture. For an
app that handles patient health data, this is the single largest
structural gap found in the audit — bigger than any individual code bug,
because it means the actual access-control enforcement for the entire
system is unauditable from this repository.

**Effort**: Medium (mostly one-time setup + migrating existing state).

**Implementation**:
1. Install the Supabase CLI locally: `npm install -g supabase` (or use
   `npx supabase`).
2. `supabase login`, then `supabase link --project-ref <your-ref>` from
   the repo root.
3. Pull the CURRENT live schema and policies into a baseline migration:
   `supabase db pull` — this generates
   `supabase/migrations/<timestamp>_remote_schema.sql` capturing exactly
   what's live today (tables, columns, RLS policies, triggers, the
   `triage_priority` generated column, the Realtime publication). Review
   this file carefully — it's your ground truth for what's actually
   deployed.
4. Commit `supabase/` (config.toml + migrations/) to the repo. Add a
   `supabase/.gitignore` entry for `.branches/` and any local-only state
   per Supabase CLI docs.
5. From this point forward, EVERY schema or RLS change goes through:
   `supabase migration new <descriptive_name>` → hand-write the SQL → test
   against a local Supabase instance (`supabase start` / `supabase db
   reset`) → `supabase db push` to apply to the linked project → commit the
   migration file. Never edit the schema via the Supabase dashboard UI
   directly again except in a genuine emergency, and if you do, immediately
   follow up with `supabase db pull` to reconcile.
6. Update `AGENTS.md`'s Database section to state this as the required
   workflow (mirroring what `ARCHITECTURE_RESTRUCTURE.md` §3.3 already
   proposed but was apparently never executed).
7. Add a CI job (or at minimum a documented manual step before merging any
   PR that touches `supabase/migrations/`) that runs `supabase db lint` and
   applies migrations to a throwaway/staging project to catch syntax errors
   before they hit production.
8. Once migrations exist, write the actual RLS policies down explicitly in
   `CODEBASE_MAP.md` §5 replacing the "inferred, not authoritative" caveat
   with real policy descriptions.

**Acceptance check**: A fresh Supabase project, given only this repo and
`supabase db push`, should end up with an access-control posture
identical to production.

---

### 1.2 Golden-vector Python/JS feature-engineering parity test (CI-enforced) — ✅ DONE

**Status**: Implemented. `backend/scripts/export_golden_vectors.py` generates
240 synthetic patients across all four severities and writes
`tests/fixtures/golden_feature_vectors.json` (mirrored into
`frontend/tests/fixtures/`); `backend/tests/test_feature_parity.py` and
`frontend/tests/featureParity.test.mjs` both replay it, wired into
`.github/workflows/ci.yml`'s PR and push frontend jobs alongside the existing
tree-parity check. This immediately caught a real bug (see
`backend/app/ml/README.md`): `buildFeatureMap()` was clamping a real age of 0
(a newborn) up to a 40-year-old default before several age-banded risk
checks, so newborns received adult-cardiac/obstetric scoring instead of
pediatric-fever scoring in the offline path only — fixed by introducing a
second age variable (`ageOrDefault`) that only substitutes on a truly-missing
age, matching `clinical_features.py`'s own `.get('patient_age', 40)` pattern.

**Why (original)**: `backend/app/ml/clinical_features.py::ClinicalFeatureEngineer` is
hand-ported into `frontend/src/utils/triageClassifier.js::buildFeatureMap()`.
If a future change to one is not mirrored in the other, the offline
(browser) triage classification silently diverges from the online (server)
classification for the same patient data — a real clinical-safety risk
that would produce no error, no warning, just a different EMERGENCY/URGENT/
ROUTINE result depending on whether the ASHA worker happened to be online
or offline at submission time. This is exactly the class of bug the recent
audit fixed once already (the previous two-model architecture had this
problem structurally); a parity test prevents it from being reintroduced
one feature at a time.

**Effort**: Small.

**Implementation**:
1. Create `backend/scripts/export_golden_vectors.py`: generates ~200
   diverse synthetic patients (reuse `generate_patient()` from
   `train_classifier.py`), runs each through
   `ClinicalFeatureEngineer.engineer_features()`, and writes
   `backend/tests/fixtures/golden_feature_vectors.json` — a list of
   `{ "input": {...raw patient dict...}, "features": {...45 named values...} }`.
2. Add `backend/tests/test_feature_parity.py`: loads the golden fixture,
   re-runs `ClinicalFeatureEngineer.engineer_features()` on each `input`,
   and asserts the output matches the recorded `features` exactly (this
   catches accidental Python-side regressions too, not just JS drift).
3. Add a small Node-side test harness: `frontend/tests/featureParity.test.js`
   (or reuse Playwright's component-testing if already configured) that
   imports `buildFeatureMap` from `triageClassifier.js`, loads the same
   `golden_feature_vectors.json` fixture (copy or symlink it into
   `frontend/tests/fixtures/`), and asserts each computed feature map
   matches the recorded Python output within a small floating-point
   tolerance (`Math.abs(a - b) < 1e-6`).
4. Wire both into `.github/workflows/ci.yml` as required jobs. Because
   `buildFeatureMap` has no external dependencies (pure computation), this
   test needs no Supabase secrets and can run fast on every PR.
5. Document in `backend/app/ml/README.md`: "Before merging any change to
   `clinical_features.py`, regenerate the golden fixture
   (`python scripts/export_golden_vectors.py`) and port the equivalent
   change to `triageClassifier.js::buildFeatureMap()` — CI will fail
   otherwise."

**Acceptance check**: Deliberately introduce a one-line discrepancy between
the Python and JS feature engineering in a scratch branch; confirm CI fails
on it.

---

### 1.3 Doctor outcome feedback loop + real-data model retraining — ✅ DONE

**Status**: Fully implemented. `case_outcomes` table (migration `phase17_...`,
immutable/insert-only via RLS), `PATCH /api/cases/{case_id}/outcome`
(`CaseOutcomeInput`-validated, same facility-scoping as `review_case`), a
"Record patient outcome" control on `BriefingCard.jsx` (shown once a case is
reviewed), `scripts/retrain_from_outcomes.py` (blends recorded outcomes with
a shrinking proportion of synthetic data, trains a candidate model, reports
its agreement rate against the recorded outcomes vs. the current production
model's — never auto-promotes; saves to `candidate_triage_classifier.pkl`
for human review), and `GET /api/analytics/ml-agreement` + an "ML Triage
Agreement" card on the admin System tab.

Verified end-to-end against `tests/fixtures/synthetic_outcomes.json` (75
synthetic outcomes with ~15% simulated doctor/model disagreement, via
`--force` to bypass the production minimum-sample-size gate): the candidate's
agreement with the recorded outcomes measurably exceeded the untouched
production model's (0.947 vs 0.867) — the acceptance criterion. The
retraining script is deliberately **not** wired into CI (per its own spec —
a silently-regressing clinical model in production is worse than a slower
manual cadence) and is slow (~30-60s, generates the full 36k-patient
synthetic pool) — run it manually, not as part of the fast test suite.

**Why (original)**: The classifier is currently trained entirely on synthetic,
evidence-informed-but-unvalidated data (see `backend/app/ml/README.md`).
There is no mechanism to learn from what actually happened to patients —
the single highest-leverage improvement available for genuine clinical
accuracy is closing that loop. This is also the properly-scoped successor
to the old `ContinualLearningManager` stub that was removed during the
audit for being entirely inert (see `backend/CLASSIFIER_CHANGELOG.md`) —
this spec is what "wiring it up properly" looks like.

**Effort**: Medium-large (new table, new endpoint, new UI, and a
periodic — not real-time — retraining job).

**Implementation**:
1. **Schema** (via a migration, see §1.1): new table `case_outcomes`:
   `id`, `case_id` (FK → `case_records.id`), `recorded_by` (FK → doctor's
   user id), `actual_severity` (`ROUTINE`/`URGENT`/`EMERGENCY` — what the
   case turned out to actually be, in the doctor's clinical judgment,
   which may differ from the ML triage), `outcome_notes` (free text,
   bounded length), `patient_disposition`
   (`treated_discharged`/`admitted`/`referred_higher_facility`/`deceased`/`unknown`),
   `recorded_at`. RLS: doctors/admins can insert for cases in their scope;
   nobody can update/delete (immutable audit trail — corrections are new
   rows, not edits, matching medical record conventions).
2. **Backend endpoint**: `PATCH /api/cases/{case_id}/outcome` in
   `app/api/routes/cases.py`, `require_role('doctor', 'admin')`,
   rate-limited like the other case routes. Validates `actual_severity` and
   `patient_disposition` against the fixed enums via a new Pydantic model
   in `schemas.py` (`CaseOutcomeInput`).
3. **Frontend**: add an "Record Outcome" action to `BriefingCard.jsx`,
   shown only after a case is marked reviewed. A small form (severity
   dropdown pre-filled with the ML's original triage_level as the default,
   disposition dropdown, notes textarea) posting to the new endpoint via a
   new `recordCaseOutcome()` wrapper in `frontend/src/api/cases.js`.
4. **Retraining pipeline** (NOT real-time, NOT automatic — a human-gated
   periodic job, given the safety stakes): a new script
   `backend/scripts/retrain_from_outcomes.py` that:
   - Pulls all `case_outcomes` joined with their `case_records` (need
     `bp_systolic`, `spo2`, etc. — the original submitted vitals).
   - Where `actual_severity` disagrees with the original `triage_level`,
     treat `actual_severity` as a higher-confidence label (real clinical
     judgment beats the synthetic-data-trained heuristic).
   - Blend this real-outcome set with a (smaller, over time) proportion of
     the synthetic dataset from `train_classifier.py`'s generator, so the
     real signal dominates as volume grows but the model doesn't overfit
     to a small early sample.
   - Retrains via the same `HistGradientBoostingClassifier` pipeline,
     produces candidate artifacts (`.pkl` + `triage_trees.json`), and —
     critically — runs the candidate against the full existing test suite
     (`tests/test_direct.py`, `tests/test_classifier_safety.py`, the JS
     parity test, plus a regression check against the last N
     production `case_outcomes`) before it's eligible for deployment. A
     human (not a cron job) reviews the accuracy/recall diff and decides
     whether to promote the candidate.
   - This is intentionally NOT wired into a CI/CD auto-deploy path. A
     clinical model regressing silently in production is a much worse
     failure mode than a slower manual review cadence (e.g. monthly, once
     there's enough outcome volume — start requiring a minimum sample size,
     e.g. 500 outcomes with at least 50 EMERGENCY-tier disagreements,
     before the first real retraining run is meaningful).
5. **Admin visibility**: extend `AdminStats.jsx` / `AnalyticsDashboard.jsx`
   with an "ML triage agreement rate" metric (% of outcomes where
   `actual_severity == triage_level`), broken out by tier — this is the
   dashboard that tells you when it's time to retrain, and doubles as an
   ongoing model-quality monitor even before the first retrain.

**Acceptance check**: A doctor can record an outcome that disagrees with
the ML triage; the disagreement is visible in an admin metric; running
`retrain_from_outcomes.py` against a synthetic `case_outcomes` fixture
produces a model that measurably shifts toward the recorded outcomes.

---

### 1.4 Web Push notifications for EMERGENCY cases

**Why**: Today, a doctor only learns about a new EMERGENCY case if their
dashboard tab is open and they notice the toast (`Dashboard.jsx`'s
`useRealtimeCases` `onInsert` handler). If the tablet's screen is off, the
browser tab is backgrounded or closed, or the doctor is away from the
device — which, for a single PHC doctor covering a facility, is much of
the working day — a life-threatening case can sit unseen. This is the
single biggest gap between "the system detected an emergency" and "a human
knows about it," which is the entire point of a triage system.

**Effort**: Medium (Web Push requires a backend push service + VAPID keys
+ frontend permission UX, but `vite-plugin-pwa`/Workbox already provides
the service worker infrastructure to hang this off of).

**Implementation**:
1. **Backend**: new table `push_subscriptions` (`user_id`, `endpoint`,
   `p256dh_key`, `auth_key`, `created_at`, `facility_id` for filtering).
   New endpoints `POST /api/push/subscribe` and `DELETE
   /api/push/subscribe` (`require_role('doctor', 'admin')`) in a new
   `app/api/routes/push_routes.py`.
2. Generate VAPID keys once (`web-push generate-vapid-keys` via the
   `pywebpush` Python package or the `web-push` Node CLI), store as new
   backend env vars `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/`VAPID_SUBJECT`
   (add to `.env.example` and `config.py::Settings`).
3. In `cases.py::submit_case`, after a successful EMERGENCY-tier upsert,
   fire-and-forget a push notification to all `push_subscriptions` rows
   matching the case's `facility_id` (or all doctors if `facility_id` is
   null) using `pywebpush`. Do this as an `asyncio` background task
   (`BackgroundTasks` from FastAPI) so it never adds latency to the
   ASHA worker's submission response.
4. **Frontend**: add a `frontend/src/lib/push.js` helper: requests
   Notification permission, subscribes via
   `registration.pushManager.subscribe({ userVisibleOnly: true,
   applicationServerKey: VITE_VAPID_PUBLIC_KEY })`, posts the subscription
   to the backend. Trigger this from `DoctorPanel.jsx` on mount with a
   dismissible prompt (don't force it — some doctors may decline, that's
   fine, Realtime-while-open still works as the primary channel).
5. Extend the service worker (the `vite-plugin-pwa` config in
   `vite.config.js`) with a `push` event handler (Workbox supports
   injecting custom SW code via `injectManifest` mode, or add a small
   custom `public/sw-push.js` imported via `importScripts` in
   `generateSW` mode) that shows a `Notification` with the patient's
   triage summary and a click-to-open action targeting the dashboard.
6. Handle subscription expiry: if a push send returns 410 Gone, delete
   the stale `push_subscriptions` row server-side.

**Acceptance check**: With the dashboard tab closed and the browser
backgrounded, submitting an EMERGENCY case produces an OS-level
notification within a few seconds.

---

### 1.5 Facility response-time SLA dashboard — ✅ DONE

**Status**: Implemented. `GET /api/analytics/response-times` (same
facility/admin scoping as `get_summary`) computes per-tier median/p90 review
latency over the last 30 days plus an "overdue" count (EMERGENCY >15 min,
URGENT >2h, ROUTINE >24h, still unreviewed) using `statistics.median` and a
nearest-rank percentile helper — no percentile math pushed into PostgREST.
New section in `AnalyticsDashboard.jsx` rendering median/p90 per tier with
the overdue count in the emergency color when non-zero. The §1.4 escalation
follow-on (re-notify past threshold) needs push notifications first — not
built this pass (see §1.4/§1b.2, still speculative pending the Web Push
implementation).

**Why (original)**: VitalNet already records everything needed for this
(`created_at`, `reviewed_at`, `triage_level`) but never surfaces it. "How
long did it take from an EMERGENCY case being flagged to a doctor actually
reviewing it" is arguably the single most important operational metric a
health system administrator can track for a triage tool — it's the
number that tells you whether the tool is actually improving patient
outcomes or just generating data nobody acts on fast enough.

**Effort**: Small (pure aggregation over existing data, no schema change).

**Implementation**:
1. New backend endpoint `GET /api/analytics/response-times` in
   `analytics_routes.py` (same facility/admin scoping pattern as
   `get_summary`): computes, per triage tier, the distribution of
   `reviewed_at - created_at` for reviewed cases in the last 30 days
   (median, p90, and count of cases still unreviewed past a threshold —
   e.g. EMERGENCY cases unreviewed after 15 minutes, URGENT after 2 hours).
   Use Python (`statistics.median`) over the fetched rows rather than
   trying to push percentile math into a PostgREST query.
2. Frontend: new `getResponseTimes()` wrapper in `api/analytics.js`, new
   section in `AnalyticsDashboard.jsx` — a small table/bar-chart per tier
   showing median/p90 response time, with the "still overdue" count
   rendered in the emergency color (`bg-emergency`) if non-zero, since
   that's the number that should visually demand attention.
3. Optional follow-on (pairs naturally with §1.4): use the "EMERGENCY
   unreviewed past N minutes" condition as a push-notification escalation
   trigger — re-notify, or notify a wider on-call list, if a case sits
   past the threshold.

**Acceptance check**: An admin viewing the dashboard can answer "are we
meeting our EMERGENCY response target?" without exporting raw data.

---

## Tier 2 — High value, larger effort

### 2.1 Multi-language intake form (i18n)

**Why**: VitalNet's default facility state (`admin_routes.py`'s
`CreateFacilityRequest.state` default) is Tamil Nadu, and ASHA workers
nationally work primarily in their regional language, not English. An
intake form in a worker's non-native language increases entry time and
error rate — directly counter to the tool's purpose in a time-sensitive
triage context.

**Effort**: Medium (mechanical but touches every form/panel).

**Implementation**:
1. Add `react-i18next` + `i18next` to `frontend/package.json`.
2. Extract all user-facing strings from `IntakeForm.jsx`, `Dashboard.jsx`,
   `panels/*.jsx`, `components/*.jsx` into
   `frontend/src/locales/en.json`, then produce `hi.json` (Hindi),
   `ta.json` (Tamil) as the first two targets given the Tamil Nadu default
   — professionally reviewed translations for clinical terminology are
   important here; do not machine-translate symptom/complaint labels
   without a clinician review pass, since a mistranslated symptom option
   is a patient-safety issue, not a cosmetic one.
3. Add a language switcher to `NavBar.jsx`, persisted per-user (a new
   `preferred_language` column on `profiles`, or simpler: `localStorage`
   keyed by user id, avoiding a schema change for a v1).
4. Keep clinical/technical constants (`symptoms` array values sent to the
   API, e.g. `"chest_pain"`) as stable English identifiers — only the
   *displayed labels* are translated; the wire format and ML feature names
   never change. This keeps the backend, `ClinicalFeatureEngineer`, and
   the triage model completely untouched by this feature.
5. `document.documentElement.lang` should update with the selected
   language for accessibility/screen-reader correctness.

**Acceptance check**: A form filled out with the language set to Hindi
submits the exact same wire payload (English symptom IDs) as English mode.

---

### 2.2 Voice-to-text intake assist

**Why**: Typing speed and literacy vary widely among ASHA workers. Free-
text fields (`observations`, `known_conditions`, `current_medications`)
are exactly where voice input has the highest leverage — structured
fields (dropdowns, symptom checkboxes) are already fast to fill via touch.

**Effort**: Medium. Two implementation paths with a real tradeoff:

**Implementation** (browser-native path, ship first):
1. Add a microphone icon button next to `observations`/
   `known_conditions`/`current_medications` fields in `IntakeForm.jsx`.
2. Use the `SpeechRecognition` Web Speech API (`webkitSpeechRecognition` on
   Chrome/Android WebView, which is what most ASHA-issued Android tablets
   run) with `lang` set to match the i18n language selection from §2.1.
3. Critical constraint: `SpeechRecognition` on Chrome requires network
   connectivity by default (it calls a Google speech API) — it will
   silently fail offline. Detect this (feature-check + a connectivity
   check via `isServerReachable()`-style probe) and disable/hide the mic
   button when offline, with a tooltip explaining why, rather than letting
   a worker tap it and get nothing.
4. Always show the transcribed text in the field for the worker to review
   and edit before submit — never auto-submit voice input directly, given
   transcription error risk in a clinical context.

**Follow-on (offline-capable path, larger effort, Tier 3-adjacent)**: an
on-device WASM speech model (e.g. `whisper.cpp` compiled to WASM, or a
smaller distilled model) would remove the online-only constraint, but adds
a multi-hundred-MB-to-multi-GB model download depending on quality tier —
directly in tension with the "run on weak hardware, minimize bandwidth"
goal elsewhere in this project. Do not pursue this path without first
validating on real target devices that the model size/latency tradeoff is
acceptable; the browser-native path should ship first and be evaluated
before investing here.

---

### 2.3 Inter-facility referral workflow

**Why**: A PHC doctor's real-world action on a severe case is often not
"treat here" but "stabilize and refer to the district hospital." VitalNet
currently has no way to represent that — a case is either reviewed or not,
with no notion of where the patient went next. This connects directly to
§1.3 (outcome tracking) and is core to what "clinical workflow tool" means
beyond just triage.

**Effort**: Medium-large.

**Implementation**:
1. Schema: new table `referrals` — `case_id`, `referred_by`,
   `referring_facility_id`, `receiving_facility_id`, `reason`
   (bounded text), `urgency` (mirrors triage tiers), `status`
   (`pending`/`acknowledged`/`patient_arrived`/`completed`/`cancelled`),
   `created_at`, `updated_at`.
2. Backend: `POST /api/cases/{case_id}/refer`,
   `PATCH /api/referrals/{id}/status` (receiving facility's doctor/admin
   can advance status), `GET /api/referrals?facility_id=` (both outgoing
   and incoming views).
3. Frontend: a "Refer" action on `BriefingCard.jsx` opening a small form
   (target facility picker, populated from `adminListFacilities`-equivalent
   but filtered to active facilities of a higher tier — this requires
   adding a `facility_type`/`tier` field to distinguish sub-centre vs PHC
   vs district hospital if not already present in `facilities`).
4. A new "Referrals" tab in `DoctorPanel.jsx` showing outgoing (sent by
   this facility) and incoming (sent to this facility) referrals with
   status, using the existing `useRealtimeCases`-style pattern
   (generalize it slightly, or add a parallel `useRealtimeReferrals` hook)
   for live status updates.
5. This should integrate with §1.4's push notifications: a new incoming
   referral is exactly the kind of event a receiving facility wants to be
   pushed, not just polled.

---

### 2.4 Admin audit log — ✅ DONE

**Status**: Implemented, reusing the existing `phi_audit_log` table and
`log_phi_access()` helper (already called from every admin_routes.py mutation
as part of round-3 reconciliation) rather than a separate `audit_log` table
as originally spec'd — same shape, same purpose, avoids a duplicate audit
mechanism. `log_phi_access()` now also persists to the DB (previously
log-only; the DB write is best-effort/non-blocking so a transient failure
never breaks the calling request). New `GET /api/admin/audit-log` (paginated,
admin-only) and an "Audit Log" tab in `AdminPanel.jsx`.

**Why (original)**: `admin_routes.py` lets an admin change any user's role, deactivate
accounts, and create/toggle facilities — all currently unlogged beyond
whatever Supabase's own database logs capture (not queryable from the
app). For a system managing access to patient health data, "who changed
this doctor's role to admin, and when" needs to be answerable from within
the product, not by asking a DBA to grep Postgres logs.

**Effort**: Small-medium.

**Implementation**:
1. Schema: `audit_log` table — `id`, `actor_id`, `action` (short enum-like
   string, e.g. `user.role_changed`, `user.deactivated`,
   `facility.created`), `target_type`, `target_id`, `metadata` (JSONB —
   e.g. `{"old_role": "asha_worker", "new_role": "admin"}`), `created_at`.
   RLS: insert-only for the backend's service-role client, select-only for
   `admin` role, no update/delete from any client (immutable).
2. Backend: a small helper `app/core/audit.py::log_action(actor_id,
   action, target_type, target_id, metadata)` that inserts via
   `supabase_admin` (bypassing RLS, since it's a system-level write). Call
   it from every mutating handler in `admin_routes.py`
   (`create_user`, `update_user`, `deactivate_user`, `reactivate_user`,
   `create_facility`, `toggle_facility`) — this is a mechanical addition
   to each existing function, not a redesign.
3. New endpoint `GET /api/admin/audit-log` (paginated, same cursor
   pattern as `get_cases`) and a new "Audit Log" tab in `AdminPanel.jsx`
   rendering a simple chronological table.
4. Retention: decide and document a retention policy (e.g. keep
   indefinitely, or purge after N years per applicable Indian health-data
   retention regulations) — this is a policy decision, flag it for
   product/legal sign-off rather than defaulting silently.

---

## Tier 3 — Large scope, needs a product decision first

### 3.1 SMS-based zero-connectivity fallback submission

**Why**: The offline-first PWA queue (`offlineQueue.js`/`syncStore.js`)
handles "no connectivity right now, will sync later" well — but it
assumes the device eventually regains internet connectivity. In genuinely
remote areas, a worker's device may go days without data connectivity
while still having basic cellular voice/SMS coverage (SMS towers have far
greater rural range than data). A structured-SMS fallback (a fixed-format
text message parsed server-side into a minimal case record: age, sex, top
1-2 symptoms, a phone-number-based patient reference) would extend
coverage to that population, at the cost of a much smaller feature set per
submission (no full 45-feature triage — an SMS can't carry vitals
practically).

**Why Tier 3, not Tier 1/2**: This needs a product decision on scope (what
minimal fields justify the engineering cost of an SMS gateway integration,
which carrier/aggregator to use in India, and the cost model — SMS
aggregators charge per message, unlike data which is closer to free at
the margin once a device has any connectivity at all). Needs a
telecom/SMS-gateway vendor decision (e.g. a licensed Indian SMS aggregator
supporting two-way SMS) before implementation specs are meaningful.

**High-level shape** (once scoped): a webhook endpoint receiving inbound
SMS from the chosen aggregator, a strict fixed-format parser (reject
malformed messages with an auto-reply explaining the correct format rather
than silently dropping them), mapping to a reduced-feature triage call
(the classifier already handles missing vitals gracefully via
`ClinicalFeatureEngineer`'s `-1`/default-fallback logic, so a
symptoms-and-demographics-only submission is already supported by the
existing model — this is more of an intake/transport problem than a
triage-logic problem), and an SMS reply carrying the triage result.

---

### 3.2 Patient photo attachments

**Why**: Visual symptoms (rashes, wounds, swelling) are hard to describe
in a structured form and a photo meaningfully helps the reviewing doctor.

**Why Tier 3, not Tier 2**: Needs product decisions on: storage (Supabase
Storage vs external), retention/consent policy for patient photographs
specifically (a materially more sensitive data category than structured
vitals, likely triggering stricter regulatory handling under Indian health
data rules), and bandwidth impact (photo upload is a poor fit for the
offline-first low-bandwidth design center — needs explicit compression/
resize-before-upload and a clear UX for "this will sync when connectivity
allows, may take a while on a slow connection").

**High-level shape** (once scoped): client-side image compression before
it ever touches IndexedDB (a full-resolution photo in the offline queue
would blow past reasonable IndexedDB storage budgets fast — resize to
something like 1024px max dimension, JPEG quality ~0.6, before enqueueing),
a new `case_attachments` table + Supabase Storage bucket with RLS matching
`case_records` access rules, and a queued-upload path in `syncStore.js`
parallel to the existing case-submission queue.

---

## Tier 1b — Round-2 additions (specs; not yet built)

These emerged from the second hardening pass. They are documented as
ready-to-execute specs (per the decision to keep new features as specs this
round). 1b.1 is the highest-value follow-on to the round-2 ML work.

### 1b.1 Doctor triage-override + reason capture (unlocks real-label collection) — ✅ DONE

**Status**: Implemented. Migration `phase17_triage_provenance_and_override.sql`
adds the nullable columns; `PATCH /api/cases/{case_id}/triage-override` in
`cases.py` (schema-validated via `TriageOverride`, same facility-scoping as
`review_case`); `BriefingCard.jsx` has an inline override control showing the
adjusted tier + reason with visible provenance once saved.

**Why (original)**: Round 2 added a `low_confidence` abstention flag and a deterministic
NEWS2 floor, but the model still has no way to learn from a doctor disagreeing
with its triage. Letting a reviewing doctor override the ML triage and record a
one-line reason is the single smallest change that starts accumulating real,
expert-labelled disagreement data — the exact input the outcome-retraining loop
(§1.3) needs. It also improves day-to-day trust: a doctor who can correct the
tool uses it more readily than one who cannot.

**Effort**: Small.

**Implementation**:
1. Schema (migration, see §1.1): add nullable columns to `case_records`:
   `overridden_triage` (text, one of the tiers), `override_reason` (text,
   bounded), `overridden_by` (fk user), `overridden_at` (timestamptz). Nullable
   so existing rows are unaffected. Also add the round-2 `triage_low_confidence`
   boolean column here (see 1b.5) so the doctor UI can show the flag the backend
   already computes.
2. Backend: `PATCH /api/cases/{case_id}/triage-override` in `cases.py`,
   `require_role('doctor', 'admin')`, same facility-scoping as `review_case`,
   rate-limited. A new `TriageOverride` Pydantic model validates the tier enum
   and reason length. Persist via the user-scoped client (RLS).
3. Frontend: an "Override triage" control on `BriefingCard.jsx` (tier dropdown
   pre-filled with the ML triage, reason textarea) posting via a new
   `overrideTriage()` wrapper in `api/cases.js`. Show the overridden tier with a
   visible "adjusted by Dr. X" marker so the provenance is never hidden.
4. This is the data source `retrain_from_outcomes.py` (§1.3) reads — the two
   specs are designed to compose.

### 1b.2 Unreviewed-EMERGENCY deterioration re-alert

**Why**: An EMERGENCY case that sits unreviewed past a threshold is the exact
failure the tool exists to prevent. §1.5 surfaces this as a dashboard metric;
this turns it into an active escalation.

**Implementation** (pairs with the §1.4 push spec):
1. A periodic backend job (or a Supabase scheduled function) scans for
   `triage_level = 'EMERGENCY' AND reviewed_at IS NULL AND created_at < now() -
   interval '15 min'`.
2. For each, re-emit a push (§1.4) to the facility's doctors, escalating to a
   wider on-call list on a second threshold. Record `last_escalated_at` to avoid
   duplicate spam.
3. No new user-facing surface required beyond the existing dashboard + push.

### 1b.3 Case CSV / PDF export for facility reporting

**Why**: PHC/district administrators must submit periodic reports up the
health-system chain. Today that means manual re-entry from the dashboard. A
scoped export is low-effort and removes a real recurring chore.

**Implementation**:
1. Backend: `GET /api/analytics/export?from=&to=&format=csv|pdf`
   (`require_role('doctor', 'admin')`, facility-scoped, rate-limited). CSV via
   the stdlib `csv` module streamed as a response; PDF via a lightweight server-
   side generator (e.g. `reportlab`) — keep columns to non-identifying
   aggregates unless an explicit, separately-authorised "line list" scope is
   requested (patient-level export is a data-governance decision — gate it).
2. Frontend: an "Export" control on the analytics view with a date range and
   format toggle, calling a new `exportCases()` wrapper.
3. Governance: document who may export line-level (patient) data vs aggregates,
   and log every export via the §2.4 audit log.

### 1b.4 Bulk ASHA onboarding via CSV

**Why**: Standing up a new facility means creating many ASHA accounts. The admin
UI creates them one at a time. A CSV import makes facility rollout practical.

**Implementation**:
1. Backend: `POST /api/admin/users/bulk` (`require_role('admin')`, stricter rate
   limit) accepting a validated list (reuse `CreateUserRequest` per row, cap the
   batch size, and return a per-row success/error report rather than failing the
   whole batch on one bad row). Reuse the existing `create_user` logic per row.
2. Frontend: a CSV upload + preview/validate step in `AdminUsers.jsx` before
   committing, showing which rows will succeed/fail.
3. Security: enforce the same 12-char password policy per row; never echo
   passwords back in the result report.

### 1b.5 Model-version display + per-case model provenance — ✅ DONE

**Status**: Implemented. `triage_model_version` column added (migration
`phase17_...`), populated in `submit_case` from `run_triage()`'s existing
`model_version` field, shown on `BriefingCard.jsx` next to the timestamp
(`low_confidence` was already added and surfaced in round 3's reconciliation,
under that name rather than `triage_low_confidence` — same thing, no
duplicate column). The admin System tab already showed `/api/health`'s model
version pre-existing this change.

**Why (original)**: Once the model retrains from real outcomes (§1.3), different cases will
have been triaged by different model versions. A doctor auditing an old case, or
an admin investigating a mis-triage, needs to know *which* model produced it.
The backend already returns `model_version` from `predict_triage`; it just isn't
persisted or shown.

**Implementation**:
1. Schema: add `triage_model_version` (text) and `triage_low_confidence`
   (boolean) columns to `case_records` (the latter shared with 1b.1). Populate
   them in `cases.py::submit_case` from the `run_triage` result.
2. Frontend: show the model version + the low-confidence flag as small metadata
   on `BriefingCard.jsx`. Show the current loaded model version in the admin
   System tab (it's already in `/api/health`).
3. This closes the loop with the audit/traceability posture and is a
   prerequisite for trustworthy A/B comparison of model versions.

---

## Explicitly out of scope for this roadmap

- **Native mobile app (React Native/Flutter)**: the PWA approach
  (installable, offline-capable, works in a plain browser) is the right
  fit for this deployment context — avoiding app-store distribution
  friction matters more for rural health-worker deployment than any native
  capability gap. Revisit only if a specific hardware capability PWAs
  cannot reach (e.g. deep background sync guarantees) becomes a blocker.
- **Telemedicine video consultation**: a fundamentally different
  bandwidth/latency profile than everything else in this app; out of
  scope unless a specific facility connectivity tier can reliably support
  it, which is a deployment-context question, not an engineering one.
