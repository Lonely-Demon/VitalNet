# VitalNet — Architecture Decisions

Why key parts of this system are built the way they are, consolidated in
one place. `CODEBASE_MAP.md` tells you *what* exists and *where*; this file
tells you *why*, including alternatives that were considered and rejected —
so a future change doesn't accidentally re-introduce a problem that was
already solved and moved past.

Add a new entry here whenever you make a non-obvious architectural choice,
especially one you expect someone to question or "simplify" later.

---

### 1. Hybrid JWT verification (local + network fallback), not pure network verification

**Context**: Supabase Auth issues JWTs. The naive approach — call
`supabase.auth.get_user(token)` on every request — makes a network
round-trip to Supabase on the hot path of *every authenticated request*.

**Decision**: `app/core/auth.py::get_current_user()` verifies the JWT
signature/`exp`/`aud` **locally** (HS256 via `SUPABASE_JWT_SECRET`) first —
no network call. It falls back to the network `get_user()` call only when
local verification can't apply (asymmetric-key/ES256 Supabase projects).
Role/`facility_id`/`is_active` are then resolved fresh from the `profiles`
table on every request, but that result is cached per-user for
`revocation_recheck_seconds` (default 300s) rather than re-queried every
single time.

**Consequences**: removes a full network round-trip from the hot path of
every request and removes Supabase Auth as a single point of failure for
API availability. The tradeoff: a deactivated user or role change takes
effect within the cache TTL window, not instantly — judged an acceptable
bound given the window is short and configurable, versus the alternative of
paying the network cost on every request forever.

### 2. Offline triage: pure-JS tree evaluator, not onnxruntime-web

**Context**: The trained model must run client-side for offline triage.
The original approach used `onnxruntime-web` — a ~12 MB WASM runtime — to
run the exported ONNX model in-browser.

**Decision**: Export the trained tree ensemble to a compact JSON
(`triage_trees.json`, ~1 MB) and walk it with a ~120-line dependency-free JS
evaluator (`treeEvaluator.js`) instead. A full comparative analysis (five
other options, including model-specific WASM and m2cgen) is preserved in
`FEATURES_ROADMAP.md`'s history; the short version: **the runtime choice
does not change model accuracy** — it's the same trained model either way,
verified identical via `npm run test:parity`'s golden-vector check. The
choice is purely about footprint, cold-start time, and robustness on
2 GB-class devices.

**Consequences**: ~100x smaller precached payload, no WASM-compile cold
start, cannot OOM a WASM runtime. Cost: a hand-ported evaluator instead of
a standard runtime, mitigated entirely by the CI-enforced parity tests
(`npm run test:parity` — tree-level; `npm run test:feature-parity` —
feature-engineering level). **Any change to `clinical_features.py` or
`classifier.py`'s tree logic must be mirrored in `triageClassifier.js`/
`treeEvaluator.js`/`clinicalRules.js` in the same change**, or these tests
fail CI — that failure is the system working as designed, not a false
alarm.

### 3. Layered triage: trained model + deterministic safety net + NEWS2 floor, not model-only

**Context**: A single ML model's raw `predict_proba` output is what most
triage-ML demos ship. But a boosted-tree model can, on an out-of-distribution
input, under-triage an unambiguously critical presentation (e.g. SpO2 60%
that happens to sit in a sparse region of training data).

**Decision**: Three independent layers, in order: (1) `_safety_net_check` —
hardcoded thresholds on extreme vitals/critical symptoms force EMERGENCY
regardless of what the model would say; (2) the trained model's own
prediction, if the safety net didn't already trigger; (3)
`_news2_concerning_vital` floor — never return ROUTINE if any single NEWS2
parameter scores ≥2. All three are mirrored exactly in
`frontend/src/utils/clinicalRules.js` for the offline path.

**Consequences**: this is *why* the offline engine can honestly claim
"never fails to escalate an unambiguous emergency, even for inputs the
tree ensemble never saw in training" — the safety net doesn't need the
model to have learned anything, it's a plain rule. Don't remove or weaken
any of the three layers "to simplify" — each is an independent backstop
against a different failure mode of the layer above it.

### 4. A fresh Supabase client per request, not one shared client with a swapped auth token

**Context**: It would be tempting to construct one `supabase-py` client at
module load and call `client.postgrest.auth(token)` per request to "save"
object construction cost.

**Decision**: `get_supabase_for_user()` constructs a new client per
request. This was explicitly investigated and rejected as an optimization
during a mid-project reconciliation: a shared client's auth token is
mutable *state* — under concurrent requests (which FastAPI handles
routinely), one request's token-swap can race with another's in-flight
query, leaking one user's RLS-scoped data to a different user's response.

**Consequences**: a small, deliberate object-construction cost per request
in exchange for correctness under concurrency. Do not "optimize" this into
a shared/pooled client without re-solving the race condition first.

### 5. CSRF token is a shared constant, not a secret — the protection is the preflight

**Context**: `main.py::csrf_and_device_guard` requires an `X-CSRF-Token`
header matching `settings.csrf_token` on every mutating `/api/*` request.
This looks like a weak secret (it's a fixed, non-random string in
`.env.example`) if you assume the security model is "attacker can't guess
the value."

**Decision**: the actual security model is different: a browser only sends
a **custom header** after a successful CORS preflight, and the preflight
only succeeds from an origin in `allow_origins`. A cross-site form/fetch
from an unlisted origin cannot attach `X-CSRF-Token` at all, regardless of
whether the value is secret. Bearer-token auth already stops a naive CSRF
attack; this header is defense-in-depth against a *misconfigured* CORS
policy, not a secret to protect.

**Consequences**: don't "fix" this by making the token cryptographically
random per-session — that solves a threat model this design doesn't
target, and would require plumbing token issuance/rotation for no real
security gain. `X-Device-Id` is unrelated: it's a stable per-browser id for
future abuse/anomaly detection, not a security boundary by itself either.

### 6. `client_id` upsert as the offline-queue idempotency key

**Context**: A submission queued in IndexedDB while offline may be retried
(app restart, sync-loop retry after a partial failure). Retrying a plain
`INSERT` would create duplicate case records.

**Decision**: every `IntakeForm` carries a client-generated `client_id`
(UUID). `submit_case` upserts on `client_id` with
`ignore_duplicates=True` — a retried submission with the same `client_id`
is silently absorbed rather than duplicated, and the original response is
looked up and returned.

**Consequences**: this is the mechanism that makes the entire offline-first
sync design safe to retry blindly. Never remove `client_id` uniqueness or
change the upsert conflict target without re-verifying retry-safety.

### 7. Service-role admin client: `require_role('admin')` is the *only* boundary

**Context**: `app/api/routes/admin_routes.py` uses `supabase_admin` (the
service-role client), which bypasses Row Level Security entirely — RLS
policies on `profiles`/`facilities`/`case_records` simply don't apply to
these queries.

**Decision**: accepted as intentional (admin operations are inherently
global/cross-tenant and RLS is user-scoped by design), but this means the
`require_role('admin')` dependency on every route in that file is **the
entire access-control boundary** — there is no RLS backstop if one is ever
missing from a new route. `tests/test_admin_authz.py` asserts this
mechanically (walks every route in `admin_routes.py`, fails CI if any
lacks `require_role('admin')` exactly).

**Consequences**: any new route added to `admin_routes.py` **must** carry
`require_role('admin')` — there's no safety net if it doesn't, other than
the test. Don't add a new admin route in a hurry without it.

### 8. Rate-limit key: the cryptographically verified JWT `sub`, not client IP

**Context**: The naive `slowapi` setup keys rate limits by client IP —
fails badly behind NAT (a whole clinic sharing one egress IP shares one
rate budget) and is spoofable in the other direction (forge a token
claiming to be another user's `sub` to burn their budget, if the `sub`
isn't verified).

**Decision**: `cases.py::_get_user_id` extracts `sub` via
`verify_sub_for_rate_limit()` — a **signature-verified** extraction, not a
naive base64-decode of the JWT payload. Falls back to client IP only when
no verifiable token is present (unauthenticated requests, or a token whose
signature can't be verified locally).

**Consequences**: each authenticated user gets their own budget regardless
of shared IP, and an attacker cannot forge a token to throttle a victim,
since a forged token fails signature verification and falls back to being
rate-limited by the attacker's own IP instead.

### 9. Three git branches (`main`/`dev`/`test`), `dev` as the actively-developed line

**Context**: the repo previously had many stray feature/fix/integration
branches accumulating from iterative work.

**Decision**: exactly three long-lived branches. `dev` is where active
development happens (direct pushes allowed, PRs from short-lived feature
branches merge here via squash — GitHub auto-deletes the head branch on
merge). `main` is periodically synced to match `dev`'s content once it's in
a verified-good state (also PR-only, squash-only — see the branch
protection note below); it is *not* meant to be a second, independently
evolving line. `test` is a pre-production staging branch.
`.github/dependabot.yml` targets `dev`.

**Consequences**: **don't develop directly on `main`.** When `main` needs
to catch up to `dev` (e.g. because GitHub's Dependabot/security scanning
watches whichever branch is configured as the repo default, which may
still be `main`), merge `dev` into `main` — resolve the merge in favor of
`dev`'s content — rather than cherry-picking or re-doing work independently
on `main`. Both `main` and `dev` have branch protection that rejects plain
merge commits via the GitHub UI/API (`squash`/`rebase` only) — a local
`git merge` + push-to-a-branch + PR + squash-merge is the working pattern
for reconciling them; a direct `git push origin main` of a merge commit
will be rejected with `GH006`.

### 10. i18n: infrastructure built, translations deliberately left as English placeholders

**Context**: FEATURES_ROADMAP §2.1 calls for Hindi/Tamil translations of
the intake form. An AI agent or a developer without clinical-translation
expertise machine-translating symptom/complaint labels is a patient-safety
risk, not a cosmetic one — a mistranslated symptom option changes what a
worker believes they're recording.

**Decision**: `react-i18next` is fully wired (language switcher, persisted
preference, `document.lang` updates, `IntakeForm.jsx` fully using
translation keys) but `hi.json`/`ta.json` are byte-for-byte copies of
`en.json` — see `frontend/src/locales/README.md`. Only a clinician review
pass should populate real translations.

**Consequences**: selecting Hindi/Tamil today changes `document.lang` and
persists the preference but every string is still English — this is
intentional, not a bug. Don't "finish" this by machine-translating the
locale files; that's the exact risk this decision avoids.

### 11. Tier 3 (SMS fallback, photo attachments): scaffolding only, no live endpoints

**Context**: both features need a product/vendor decision an engineering
pass alone can't make — which SMS aggregator (determines the actual
webhook payload shape and signature-verification scheme), and a storage
backend + retention/consent policy for patient photographs (a more
sensitive data category than structured vitals).

**Decision**: build only the vendor-independent parts — `app/services/
sms.py`'s gateway interface + strict inbound-format parser (tested), and
the `case_attachments` schema + `imageCompression.js` client utility. No
live `/api/sms/inbound` or upload endpoint exists. Wiring either up is a
small, mechanical follow-on once the blocking decision is made — don't
guess at a vendor's API shape or a consent policy to make the feature
"complete" prematurely.

### 12. Golden-vector ML parity tests freeze the clock

**Context**: two engineered features (`time_of_day_risk`, `seasonal_risk`)
are computed from `datetime.now()`/`new Date()` — a real, intentional
clinical signal (off-hours short-staffing, seasonal disease patterns), not
a bug. This makes a frozen fixture file inherently unstable: the fixture
records a value computed at generation time, but the parity tests
recompute live at whatever moment they happen to run.

**Decision**: `scripts/export_golden_vectors.py`, `tests/
test_feature_parity.py`, and `frontend/tests/featureParity.test.mjs` all
pin the same `FROZEN_REFERENCE_TIME` (noon, July 4) via a monkeypatched
`datetime`/`Date`, so recomputation is deterministic regardless of real
wall-clock time.

**Consequences**: this bug was real and did fire mid-development (both
Python and JS parity tests failed identically — confirming they still
agreed with *each other*, just not with a stale fixture). If you add a new
time-dependent engineered feature, you must extend this freeze to cover it
or the same flakiness returns.

### 13. CodeQL suppression uses `codeql[query-id]`, not the legacy `lgtm[query-id]`

**Context**: two intentional-and-reviewed findings (the PHI audit-trail
logger; synthetic-fixture prints in a manual test script) were originally
annotated with lgtm.com's legacy suppression comment syntax.

**Decision**: GitHub's current default CodeQL setup does not honor
`lgtm[query-id]` — only `codeql[query-id]`, placed on the exact flagged
line (not just somewhere nearby). Both occurrences were fixed to the
correct syntax.

**Consequences**: if a future PR shows a CodeQL alert on a line you believe
is already-reviewed/accepted, check the suppression comment's syntax and
exact placement before assuming the finding is new.

### 14. Offline-emergency SMS alert carries no PHI, by design

**Context**: VitalNet's original design intent (predating this repo's
current hardening passes) included an offline fallback: if an ASHA
worker's device is offline and the on-device triage is EMERGENCY, the case
sits in the sync queue until connectivity returns — which in a low-signal
area could be hours. That gap was never closed until this pass
(`EmergencySmsAlert.jsx`, wired into `IntakeForm.jsx`'s queued-result view).

**Decision**: the alert is a plain `sms:` URI intent (an `<a>` tag, not a
network call) pre-filled with a **fixed, generic workflow-ping message**
that names no patient, no vitals, and no diagnosis — just "an
EMERGENCY-classified case is queued offline, please check the queue." SMS
is unencrypted and often visible in a shared device's default messaging
app, so no PHI is ever placed in the body, matching the third guardrail
layer in `docs/CLINICAL_GOVERNANCE.md` (mandatory uncertainty/limits
signalling) and the fifth (accountability separation — this is a workflow
ping, explicitly not a clinical handoff). The facility's contact number is
fetched once (joined onto the profile fetch in `authStore.jsx`) and cached
to `localStorage` (`vn_facility_phone`) specifically so it survives an
offline reload; if it's missing (first-ever offline session before any
online profile fetch), the `sms:` URI is left without a number and the UI
tells the ASHA worker to pick a contact manually — the button still works,
it just can't pre-address it.

**Consequences**: this is a best-effort convenience, not a guaranteed
delivery channel (no signal at all means no SMS either — that's a physical
limit no software fixes) and it is one-way and unconfirmed (no delivery
receipt is tracked). It is deliberately separate from both the Web Push
re-alert (online-only) and the Tier-3 SMS-inbound scaffolding
(`app/services/sms.py`, ASHA→backend submission direction) — three
different features that happen to share the same underlying transport.

### 15. Server-side Whisper transcription is the primary voice path; browser STT is the fallback

**Context**: VitalNet's original design intent was that the browser's
built-in speech recognizer would be a UX-layer convenience only (fast
waveform-style feedback) while a real Whisper-class model did the actual
clinical transcription — browser recognizer accuracy on Indic medical
speech was judged insufficient to be the transcript of record. The first
build of voice-to-text (`docs/DECISIONS.md`, Tier 2 §2.2) shipped with only
the browser path, because it was the faster ship-first option; this was a
deliberate scope cut at the time, not a reversal of the original intent.

**Decision**: `useVoiceInput.js` now tries `MediaRecorder` +
`POST /api/voice/transcribe` (`app/services/voice.py`, Groq
`whisper-large-v3`, reusing the already-configured `GROQ_API_KEY` — no new
credential) first, and falls back to the browser's
`SpeechRecognition`/`webkitSpeechRecognition` only if `MediaRecorder`/mic
access isn't available, or if the server call itself fails (misconfigured
key, Groq outage). No audio is persisted server-side — it's transcribed
and discarded in the same request.

**A nuance worth stating plainly**: the browser fallback is *not* a true
offline path either — Chrome's `SpeechRecognition` routes audio through a
Google speech service over the network, same as the server path. Both
transcription paths require connectivity; `useVoiceInput.js` gates on
`navigator.onLine` either way. What changed is which *online* path is
primary — Whisper for accuracy, browser recognizer as a same-cost fallback
rather than the primary — not an offline/online split.

**Consequences**: Firefox (no `SpeechRecognition`) now gets voice input for
the first time via the server path, since availability no longer requires
`SpeechRecognition` support specifically. If `GROQ_API_KEY` is unset in a
deployment, the endpoint returns `503` and the hook silently falls back to
the browser path on browsers that support it, or surfaces the existing
`unsupported`/`failed` error state on ones that don't.

### 16. Ambulance alert ships as a `tel:108` intent, not a dispatch integration

**Context**: a nearest-ambulance-dispatch feature was proposed. Research
into India's 108 emergency ambulance service (operated mainly by GVK EMRI
under contract to 17 state governments, ~9,600 ambulances) found that it
already does GPS-based nearest-ambulance dispatch **internally**, but does
not expose a public API a third-party app can call into.

**Decision**: ship only the tier that needs nobody's permission — a
`tel:108` call intent (`AmbulanceCallButton.jsx`), shown alongside the
EMERGENCY triage result exactly where `EmergencySmsAlert.jsx` already
sits, both online and offline. A self-maintained ambulance registry
(mirroring the `facilities` table) and a formal GVK EMRI dispatch
integration were both considered and explicitly **not** built: the
registry adds an ongoing maintenance burden for a resource this project's
own target areas often don't have, and the dispatch integration requires
a government partnership this codebase cannot secure by writing more code.

**Consequences**: this is a deliberately modest feature — a phone call,
not a coordinated dispatch. It works precisely because it depends on
nothing VitalNet doesn't already control (a static phone number), at the
cost of not being as capable as a real dispatch integration would be.

### 17. Contraindication flags are free-text keyword matching, not a drug database

**Context**: `known_conditions` and `current_medications`
(`app/models/schemas.py::IntakeForm`) are free text, not coded against
RxNorm/ICD or any structured drug database. A general drug-drug
interaction checker needs structured input; faking that coverage on free
text would produce false confidence, which is worse than no checker.

**Decision**: `app/ml/contraindications.py` checks a small, curated list
of well-established condition/medication/symptom combinations (NSAID +
renal disease, ACE inhibitor/ARB + renal disease, metformin + persistent
vomiting, anticoagulant + severe bleeding, beta-blocker + bradycardia,
insulin/sulfonylurea + altered consciousness) via case-insensitive
substring matching — the same technique `clinical_features.py` already
uses for `_calculate_comorbidity_risk`. A flag never changes the triage
tier; `cases.py` folds any flag into `needs_review`, the same mechanism
`human_review_requested` already uses, so a doctor looks rather than the
system silently escalating or de-escalating on an unverified match.
Mirrored 1:1 in `frontend/src/utils/clinicalRules.js` for the offline
path (`docs/DECISIONS.md` §2's parity requirement), with a dedicated
parity test (`test:contraindications`) alongside the tree/feature ones.

**Consequences**: this is advisory, not comprehensive — anything not on
the six-rule list is not checked, and the module's own docstring says so.
Extending coverage means adding another `ContraindicationRule` entry in
both languages, not building toward a general interaction engine.

### 18. Patient-facing summary restates the briefing, it never re-derives it

**Context**: `consent_captured` proves a checkbox was ticked, not that the
patient understood what's happening — a real gap between captured consent
and informed consent, especially across a language barrier.

**Decision**: `POST /api/cases/{id}/patient-summary`
(`generate_patient_summary` in `app/services/llm.py`) is a separate,
on-demand LLM call — not generated automatically on every submission
(cost/latency, `docs/SLO.md`) — that is given the ALREADY-FIXED
`triage_level` and `briefing.primary_risk_driver`/
`recommended_immediate_actions`, and asked only to restate them in short,
plain language in the requested language. It is structurally unable to
arrive at a different clinical read than what's already decided, the same
LLM-independent-triage guardrail `generate_briefing` already follows. On
any failure (no API key, timeout, empty response) it falls back to a
canned per-tier sentence rather than erroring — this is a UX nicety layered
on an already-complete case, not a step the submission flow depends on.

**Consequences**: translation quality for Hindi/Tamil depends on the LLM's
own fluency, not a maintained translation file (unlike the app's own i18n
strings, which are still English placeholders per §10) — so this can
produce real Hindi/Tamil text today even though the UI chrome around it
cannot yet. Not persisted to the database; regenerated fresh on each
request, so it never goes stale relative to a later triage override.

### 19. Facility capacity is self-reported, and needed a new RLS UPDATE policy

**Context**: the referral workflow (Tier 2) lists candidate facilities but
has no signal for whether a facility can actually take a referral right
now — VitalNet has no real bed-management system to derive that from.

**Decision**: `facilities.capacity_status` (`available`/`limited`/`full`)
is self-reported by that facility's own doctor (or any admin), via
`PATCH /api/facilities/{id}/capacity`
(`referral_routes.py::update_facility_capacity`). Because this is a mixed
doctor/admin write scoped to a single row — unlike `admin_routes.py`'s
facility CRUD, which is `require_role('admin')`-only and always uses the
RLS-bypassing `supabase_admin` — this endpoint uses the RLS-scoped
`get_supabase_for_user` client instead, which meant `facilities` needed
its first-ever UPDATE policy (only a SELECT policy existed before,
`phase15_data_security_hardening.sql`); added in
`phase22_facility_capacity.sql`, mirroring the SELECT policy's own-
facility-or-admin shape.

**Consequences**: this is advisory, like the contraindication flags — a
referring doctor sees one more signal in the facility picker
(`BriefingCard.jsx`), not a guarantee. RLS is row-scoped, not column-
scoped, so in principle a doctor with a valid token could update other
fields on their own facility's row via a direct API call, not just
`capacity_status` — accepted as consistent with how RLS is used
everywhere else in this schema (no column-level restriction attempted
anywhere), and bounded to their own facility's already-public directory
information, not another tenant's data or any PHI.

### 20. Referral load-balancing needed one narrow, deliberate RLS bypass

**Context**: ranking referral candidates by current load (so a referral
doesn't land on the already-most-overloaded facility) needs each
candidate facility's open (unreviewed) case *count*. But `case_records`'
RLS restricts a doctor's own token to their OWN facility's rows by
design — the entire point of that policy — so a doctor's RLS-scoped
client structurally cannot see another facility's case count, empty or
otherwise.

**Decision**: `list_active_facilities` (`referral_routes.py`) uses
`supabase_admin` for exactly one query — `select("facility_id")` on
unreviewed, non-deleted cases — to build a `{facility_id: count}` map,
then attaches only the integer `open_case_count` to each facility in the
response. No other column is read from that query, and no individual
case row, patient data, or free text is ever returned to the caller. The
returned facility list is sorted least-loaded first as a suggestion; the
doctor can still choose any facility.

**Consequences**: this is a deliberate, narrow exception to "supabase_admin
is only used behind require_role('admin')" (`docs/DECISIONS.md` §7,
enforced by `test_admin_authz.py` for the admin-only surfaces) — a
doctor-accessible endpoint now makes one RLS-bypassing call. The
exception is safe specifically because what crosses the RLS boundary is
an aggregate count, not PHI; if this pattern needs to be reused elsewhere,
apply the same test: never return anything from the `supabase_admin` call
beyond an aggregate a doctor is already trusted to reason about (referral
target selection).

### 21. Patient continuity uses an opaque, client-generated key — not a patient registry

**Context**: ASHA workers often see the same patient across multiple
visits, but VitalNet has no centralized patient registry (deliberately —
building one is exactly the kind of external-infrastructure scope creep
ruled out for this project), and a brand-new patient's first visit may
happen with zero connectivity.

**Decision**: `case_records.patient_key` (nullable, format `XXXX-XXXX`,
`phase23_patient_key.sql`) is generated entirely client-side
(`frontend/src/utils/patientKey.js::generatePatientKey`, `crypto.getRandomValues`)
using an alphabet that excludes 0/O/1/I/L so it's never mis-copied by hand.
It encodes no PII — it is only meaningful joined against `case_records`.
After a new patient's first submission, `PatientKeyCard.jsx` renders it as
both a QR code (`qrcode` npm package, rendered client-side via
`toDataURL`) and plain text for the worker to hand to the patient. A
returning patient's worker types the existing code back in on the next
visit (`IntakeForm.jsx`'s "Returning Patient?" field) — v1 deliberately
has no camera-based QR scanning, to keep the surface area small.
`GET /api/cases/by-patient-key/{key}` (`cases.py::get_cases_by_patient_key`)
looks up prior visits sharing a key, using the same RLS-scoped client and
the same per-role visibility boundary as every other case view in this
file (`admin` global, `doctor` own-facility, `asha_worker` own
submissions only — confirmed via `GET /api/cases/mine`'s existing
RLS-enforces-ownership comment, so an ASHA worker naturally only
recognizes patients they personally saw before, not a facility-wide
history).

**Consequences**: continuity is opportunistic, not guaranteed — a worker
who forgets to ask for the code, or a patient who loses it, starts a
fresh, unlinked record; this is accepted as a reasonable v1 limitation
rather than building a registry. The format regex is duplicated in three
places by necessity (`backend/app/models/schemas.py::PATIENT_KEY_RE`, the
`phase23` CHECK constraint, `frontend/src/utils/patientKey.js`) — covered
by `backend/tests/test_patient_key.py`.

### 22. Cross-visit deterioration alert needed the same narrow RLS bypass as §20

**Context**: once a `patient_key` links visits together (§21), a genuinely
useful signal falls out of it for free: a patient with repeated
URGENT/EMERGENCY presentations in a short window is worth a clinician's
attention even if today's individual reading looks unremarkable. But
computing "how many qualifying visits has this patient_key had recently"
hits the exact same wall as §20 — `case_records`' RLS restricts an
`asha_worker`'s own token to only cases *they personally* submitted, so if
a different worker saw this same patient last week, the submitting
worker's RLS-scoped query would silently undercount and miss the pattern.

**Decision**: `cases.py::_check_deterioration_pattern`, called once per
`POST /api/submit`, uses `supabase_admin` for exactly one count-only query
— `select("id", count="exact")` filtered to `patient_key`, a trailing
7-day window, and `triage_level IN (URGENT, EMERGENCY)`, via
`is_("deleted_at", "null")`. If the prior qualifying count plus today's
own tier reaches 2, `case_records.deterioration_alert` is set (with
`deterioration_visit_count` for context) and folded into `needs_review`
alongside the existing contraindication/low-confidence/human-requested
triggers (`phase24_deterioration_alert.sql`). Surfaced in
`BriefingCard.jsx` next to the contraindication flags.

**Consequences**: same governing test as §20 applies and is satisfied —
only an integer count crosses the RLS boundary, never a row, and the
worker submitting the case is already trusted to reason about this same
patient's recent severity (they hold the key). Deliberately backend-only:
this needs authoritative visibility across all prior visits regardless of
device, so it cannot be computed in the offline JS path — a case
submitted offline gets this check only once it syncs and calls
`/api/submit` for real.

### 23. ML classifier audit: dead contextual features, monotonic constraints (infeasible), a real parity bug

**Context**: a direct audit of the trained classifier + SHAP explainer,
requested specifically to find genuine improvement opportunities rather
than re-describe what Round 2 already built. Four findings, each verified
against the actual code/behavior rather than assumed.

**Finding 1 — two features were provably dead, two more were placeholders.**
`clinical_features.py::_engineer_contextual_features` called
`_time_based_risk()`/`_seasonal_disease_risk()` (both reading
`datetime.now()`) and hardcoded `epidemic_alert_level: 0.0`.
`scripts/train_classifier.py` generates its entire 36,000-patient training
set within one script invocation, so every training example received the
*same* value for these — `HistGradientBoostingClassifier` cannot mathematically
learn a split on a constant feature, so `time_of_day_risk` and
`epidemic_alert_level` had **zero influence on any prediction**, ever,
despite being computed on every request and listed in `FEATURE_LABELS` as
if they mattered. `_geographic_disease_risk` was a literal `return 1.0`
placeholder — also constant, also inert.

**Decision**: removed `time_of_day_risk` and `epidemic_alert_level`
outright (45 → 43 engineered features). Rebuilt `seasonal_risk` and
`geographic_risk` as real signals: `_seasonal_disease_risk` now accepts an
optional `reference_month` (monsoon June–September → 1.3, shoulder
months → 1.1, else 1.0 — India's dengue/malaria/leptospirosis season);
`_geographic_disease_risk` returns 1.2 for rural/tribal locations, 1.0
otherwise. Real submissions never set `reference_month`, so live inference
always falls back to the actual current month — the change is invisible to
production behavior except that the feature now varies. To make these
features *earn* real predictive importance (not just real variance),
`scripts/train_classifier.py::generate_patient` now samples a
`_reference_month` per synthetic patient and `_sample_symptoms` applies a
genuine probability bump (high fever, severe headache, persistent
vomiting × 1.6, capped at 0.65) when `_reference_month` is a monsoon month
**and** the patient's location is rural/tribal — mirroring the real-world
dengue/malaria surge pattern. Labels are still computed purely from the
resulting vitals/symptoms via the existing decoupled `assign_triage_label`
scorer, never directly from month/location, preserving the "label reflects
physiology, not the generation bucket" principle. Mirrored in
`frontend/src/utils/triageClassifier.js` — `buildFeatureMap` reads
`formData._reference_month` when present (fixture/test parity only, real
submissions never set it) and otherwise uses the real current month.

**Finding 2 — calibration was validated on a class-balanced set only.**
The training/test split is deliberately 33/33/33 by class (needed to learn
the rare EMERGENCY class well), but that is not VitalNet's real deployment
distribution. `train_classifier.py` now additionally subsamples the
held-out test set to a realistic ~85% ROUTINE / 12% URGENT / 3% EMERGENCY
prevalence (`_realistic_prevalence_sample`, keeping all available ROUTINE
rows and subsampling URGENT/EMERGENCY down proportionally — no new
generated data, no training-set changes) and reports ECE and the
`low_confidence` abstention rate against it, validating the *same fixed*
0.55-probability / 0.15-margin thresholds under the shape VitalNet actually
sees in the field. Both numbers are in `MODEL_CARD.md`.

**Finding 3 — monotonic constraints: investigated, verified infeasible,
not forced.** Several engineered features are constructed as unambiguous
"higher = worse" scores (`shock_index`, `sepsis_risk_score`,
`hemodynamic_instability`, `respiratory_distress_score`,
`cardiac_risk_score`) — constraining `HistGradientBoostingClassifier` to
respect that monotonically would make the model's behavior in sparse/
out-of-distribution feature space provably safe rather than merely
probable, at effectively zero training-time cost. Verified directly rather
than assumed: `HistGradientBoostingClassifier(monotonic_cst=...)` in the
pinned scikit-learn 1.9.0 raises `ValueError: monotonic constraints are not
supported for multiclass classification` for this 3-class problem. Not
applied — upgrading scikit-learn is a separate, bigger decision (this
project pins it exactly; see `app/ml/README.md`'s "why scikit-learn is
pinned exactly" section) not taken unilaterally as part of a feature-engineering
pass. Documented as a known limitation in `MODEL_CARD.md`, worth revisiting
if the pin ever moves.

**Finding 4 — a real, rare parity bug, found and fixed during retraining.**
Retraining with the Finding-1 changes intermittently (roughly 1-in-2000
held-out samples) produced a `pkl==onnx: True, pkl==treeJSON: False`
parity failure — traced to `scripts/tree_export.py` rounding ONNX split
thresholds to 6 decimal places. The new `seasonal_risk`/`geographic_risk`
features are low-cardinality and discrete (values like exactly `1.0`,
`1.1`, `1.2`, `1.3`), so a learned split threshold can land exactly on or
adjacent to one of these repeated values far more often than on the
previously near-continuous vital-sign-derived features — and rounding that
threshold to 6 decimal places occasionally flipped which side of `<=` a
real feature value fell on, diverging from onnxruntime's full-precision
comparison and flipping the argmax on a near-tied prediction. Fixed by
rounding to 9 decimal places instead (lossless versus the underlying
float32 threshold for values of this magnitude). Confirmed via a bisection
test: the original (pre-audit) code with the newly-installed
skl2onnx/onnxruntime versions passed parity cleanly, and each of Findings
1's two changes passed independently — the failure only appeared when both
were combined, which is what surfaced the latent threshold-rounding
sensitivity. This was a pre-existing bug not previously triggered by any
prior training run's feature distribution.

### 24. Voice transcription: Groq tried first, Sarvam AI as a credit-conserving fallback

**Context**: `app/services/voice.py` previously had exactly one provider
(Groq Whisper `whisper-large-v3`). The user asked to (1) bump the Groq
model to `whisper-large-v3-turbo`, and (2) add Sarvam AI — specialised
Indian-language speech-to-text — as a second provider, then to bias
provider selection toward Groq because Sarvam's free tier is a fixed
signup credit (Groq has no comparable ceiling for this app's volume) that
would otherwise be spent on requests Groq already handles adequately.

**Decision**: `voice.py` now supports two independent, optional providers.
Groq Whisper (`whisper-large-v3-turbo`) is tried first for every language.
Sarvam AI (`saaras:v3`, `POST https://api.sarvam.ai/speech-to-text`,
`api-subscription-key` header, BCP-47 language codes) is tried only if Groq
is unconfigured (`GROQ_API_KEY` unset) or a request to it raises — i.e.
purely as a fallback, never proactively for its Indian-language
specialisation. Either credential alone is sufficient for every supported
language (`en`/`hi`/`ta`); if neither is configured, or every configured
provider's request fails, `POST /api/voice/transcribe` returns `503`
exactly as before. Both API keys were verified directly against the real
endpoints (a synthetic test-tone WAV, not real speech) before this shipped,
confirming the model names and auth scheme are correct — not assumed from
documentation alone.

**Consequences**: `SARVAM_API_KEY` is a new optional setting
(`app/core/config.py`, `.env.example`) — empty disables Sarvam outright and
behavior is identical to before this change. `tests/conftest.py` explicitly
forces `SARVAM_API_KEY=""` for the test suite (mirroring the existing
`GROQ_API_KEY` fake-credential fill) so voice-transcription tests have a
deterministic "Sarvam unconfigured" starting point regardless of what a
developer's local `.env.local` carries. **Operational note**: the real
Groq/Sarvam keys used during this change were shared directly in a chat
message — both were only ever written to a local, gitignored `.env.local`
in the development sandbox, never committed; rotating both keys after this
change shipped is recommended good hygiene since they passed through a chat
transcript.

### 25. A fourth role — `supervisor` — grounded in NHM's real ASHA Facilitator structure

**Context**: the user asked for a supervisor dashboard, an outbreak
dashboard, and a protocol/guideline lookup assistant, and explicitly asked
for the role/access model ("who manages who") to be researched and decided
rather than assumed. Before building any of the three, this needed an
answer: is "supervisor" a new role, or a view bolted onto `doctor` or
`admin`?

**Research**: India's National Health Mission already has exactly this
role in the real ASHA program — the **ASHA Facilitator**. Per NHM's own
guidelines, a Facilitator provides "supportive supervision" to a cluster
of ASHA workers (roughly 10 in tribal areas, 20–25 elsewhere): joint home
visits, monthly cluster meetings, performance support. Critically, this is
a **parallel reporting line to the clinical one** — a Facilitator manages
ASHA-workforce quality and reports through block-level NHM administration,
not through a treating doctor. A PHC doctor and an ASHA Facilitator are
different people with different jobs in the real system this app models.

**Decision**: `supervisor` is a new, fourth role — not a permission bolted
onto `doctor` (would wrongly conflate clinical case authority with
workforce-quality oversight — different people, different jobs in reality)
and not onto `admin` (would wrongly hand a facility-level workforce
supervisor organisation-wide system authority, which they don't have in
NHM's real structure either). It is:

- **Facility-scoped**, the same way `doctor` already is (`resolved_facility_id`
  — no new scoping primitive needed).
- **Aggregate-only, non-PHI, read-only** by design: per-ASHA-worker
  submission counts, `needs_review` rate, contraindication-flag rate,
  deterioration-alert rate, and triage-tier distribution at their own
  facility. This is exactly the signal real supportive supervision needs
  (which workers need more training or support) and structurally cannot
  see an individual patient's case — no new PHI exposure surface at all.
- **Not** clinical review/override authority (stays `doctor`-only — a
  supervisor is not a clinician) and **not** user/facility CRUD (stays
  `admin`-only — a facility-level role has no business managing the whole
  organisation).
- Also scoped into the facility-level view of the outbreak dashboard
  (§26) and the curation queue for the protocol assistant (§27) — both are
  a natural extension of "workforce quality and support," not scope creep.

**Implementation consequence**: none of this repo's tracked migrations put
a CHECK constraint on `profiles.role`, so the original assumption here was
that adding `supervisor` needed no schema migration for the role value
itself — only extending `admin_routes.py`'s Pydantic `Literal` type +
`require_role()` calls, and the admin user-management UI. **Correction,
found during E2E verification against the live project**: the live
database in fact had a `profiles_role_check` CHECK constraint rejecting
`'supervisor'` — added directly against the project at some point, outside
version control entirely (the exact untracked-drift risk this section
originally assumed didn't apply here). Fixed and made tracked by
`phase26_role_check_constraint.sql`. New aggregate-only endpoints follow
the exact same narrow `supabase_admin` pattern already established and
governed in §20/§22 (an aggregate crosses the RLS boundary, never a row) —
supervisor is never added to `case_records`' underlying (untracked,
pre-`phase15`) row-level SELECT policy.

### 26. Outbreak dashboard — a real epidemiological method, honestly scoped

**Context**: an "internal outbreak early-warning dashboard" was one of the
four features explicitly deferred pending a decision in an earlier round.
Two questions needed answers: what algorithm, and who sees it.

**Research**: CDC's Early Aberration Reporting System (EARS) is the
standard reference for lightweight syndromic-surveillance aberration
detection, and a comparative study of small-population outbreak-detection
methods found its **C1 variant** — a 7-day trailing baseline mean and
standard deviation, flagging today's count when it exceeds
`baseline_mean + 3×baseline_stddev` — had the best validity and timeliness
specifically in **small-population settings**, which is the right
comparison class for a rural PHC's case volume (not a large-city hospital
stream). This is a real, citable, appropriately-scoped method rather than
an invented threshold.

**Decision**: implemented as a C1-style check over `(facility, symptom-or-
chief-complaint cluster, day)` aggregate counts — a floor (e.g. at least 3
cases) is also required before a day is even eligible to be flagged, so a
jump from 0 to 1 case in a tiny population is never treated as
"elevated." Output is **aggregate counts only** — no patient names, no
individual case content, ever. Scope: `admin` sees every facility;
`doctor` and `supervisor` see their own facility only (the same facility-
scoping convention used everywhere else). Framed explicitly, in the UI and
the code, as an informational aid for a human to review — not a validated
public-health surveillance system — matching the same honesty standard
already applied to `fairness_audit.py`/`drift_monitor.py`.

### 27. Protocol/guideline lookup assistant — grounded in ASHABot's own published lessons, adapted for VitalNet's constraints

**Context**: the user asked to look specifically at ASHABot (Khushi Baby +
Microsoft Research India) before designing this. ASHABot is real,
deployed, and has a published CHI 2025 paper — using its actual documented
design (not just the earlier competitive-analysis summary) materially
changed this feature's design versus a naive "let ASHA workers ask an LLM
questions" build.

**Research findings that shaped the design**:
- ASHABot uses **retrieval over a curated knowledge base** built from
  official government ASHA training modules — never raw LLM parametric
  medical knowledge. When nothing relevant is found, it answers **"I don't
  know"** rather than generating something plausible-sounding.
- Unresolved questions are escalated to human experts (Auxiliary
  Nurse-Midwives) for a crowdsourced, multi-reviewer consensus answer,
  which then updates the knowledge base for next time.
- The paper's own honestly-reported limitation: that consensus mechanism
  averaged **~60 hours** to resolve — too slow for real-time use; ASHAs
  typically found an answer elsewhere first.

**Decision**: adapt the parts of this design that transfer, and
deliberately not copy the part ASHABot's own evaluation found doesn't
work:
- **Grounding**: a small, VitalNet-authored, curated reference document
  (`backend/app/services/protocol_knowledge.md` or similar — ANC schedule,
  immunisation schedule, danger-sign checklists, common referral
  protocols) is stuffed directly into the system prompt context — a
  "RAG-lite" via context-stuffing rather than a vector database, since the
  reference material is small enough to fit directly and this avoids a new
  piece of infrastructure for a genuinely small corpus. Reuses the
  existing 4-tier Groq/Gemini fallback client, but with a **distinct
  system prompt** — never the triage-briefing prompt.
- **Never patient-specific**: the assistant refuses questions that sound
  like they're about a specific patient's symptoms ("please submit a case
  for triage instead") — this is the guardrail that stops this feature
  from reintroducing the exact expert-novice-gap failure mode VitalNet's
  own competitive research already identifies as ASHABot's real weak spot
  relative to VitalNet's triage pipeline (docs/RESEARCH_AND_DEVELOPMENT.md
  §2.5, §4.6). Answers to genuine protocol questions carry no clinical
  decision weight and never touch triage.
- **"I don't know," logged, not blocked on**: when the answer isn't in the
  reference material, the assistant says so and the question is queued
  (a new `protocol_questions` table) for asynchronous curation by a
  supervisor, doctor, or admin at the same facility — **not** a
  synchronous multi-reviewer consensus gate. ASHABot's own published data
  shows synchronous consensus is too slow to be useful; VitalNet's
  adaptation keeps the safety property (never fabricate an answer) without
  the impractical latency. A curated answer becomes part of a shared,
  growing facility FAQ inside the assistant UI.

### 28. Two free-tier keep-alive jobs — one solid, one honestly best-effort

**Context**: the project runs on free tiers end to end — Supabase (pauses a
project after 7 days with no database activity) and, for the backend, a
host like Render (spins the instance down after ~10-15 minutes idle,
causing a slow cold-start on the next real request). Both needed a
keep-alive mechanism; researched rather than assumed.

**Supabase**: `.github/workflows/supabase-keepalive.yml`, cron `17 4 */3 * *`
(roughly every 3 days — 2x safety margin under the 7-day pause threshold,
including month-boundary drift in the day-of-month step). Confirmed via
research that Supabase's inactivity timer tracks **database** activity
specifically, not dashboard visits or auth-only requests — so the job
issues a real anon-key `SELECT` against `facilities` via PostgREST (a
200/401/403 all prove the query reached the database; only a network-level
failure fails the job). This is a solid, durable fix: GitHub's documented
worst-case scheduling delay (tens of minutes) is negligible against a
multi-day threshold.

**Backend**: `.github/workflows/backend-keepalive.yml`, cron `*/10 * * * *`
hitting `GET /api/health`, per the user's explicit request. **Honestly
flagged as best-effort, not a real fix**: GitHub's own schedule trigger is
non-guaranteed — documented delays of 5-30+ minutes (sometimes worse) under
platform load are common, which can exceed a 10-15 minute host idle
timeout outright. The correct fix for this specific problem is a dedicated
uptime monitor (UptimeRobot, cron-job.org, Better Uptime, etc.) with a real
5-minute-interval SLA — noted in the workflow's own comments and here so a
future reader doesn't mistake "the job exists" for "the cold-start problem
is solved." Both workflows read their target from repo secrets/variables
(`SUPABASE_URL`/`SUPABASE_ANON_KEY` secrets, `BACKEND_HEALTH_URL` variable)
and no-op cleanly (exit 0, not a failed run) if unset — the backend one is
inert until a host is actually chosen and the variable is set.

### 29. Live E2E verification against the real project — method, two real bugs, and an ES256 finding

**Context**: after building the supervisor/outbreak/protocol-assistant
round, the user asked for an actual browser-driven E2E test rather than
relying on the pytest suite + a production build alone. This surfaced real
problems pytest structurally cannot catch (frontend/backend contract
mismatches, live schema drift) and one important operational fact about
this specific Supabase project.

**Method — sandboxed browser, no direct internet access**: this
environment's Chromium cannot reach the public internet at all (confirmed:
even a plain `https://example.com` navigation timed out, while
server-side `httpx`/`curl` through the same proxy worked fine) — a proxy
limitation specific to this sandbox, unrelated to the app. Rather than
fake the whole test, only the third-party leg was faked: a real
server-side login (`POST /auth/v1/token`) and a real profile fetch were
performed once via `httpx`, and the captured JSON was replayed into the
browser via Playwright's `page.route()` interception for exactly
`**/auth/v1/token**` and `**/rest/v1/profiles**` (with explicit CORS
response headers — Chromium enforces CORS on `route.fulfill()` responses
same as real ones, a preflight without `Access-Control-Allow-*` headers
silently blocks the real request). Every other call — all new
supervisor/outbreak/protocol endpoints, our own backend at
`localhost:8000` — went over the real network, unmodified. This is the
reusable pattern for any future live-browser test in this kind of sandbox;
see `docs/TESTING_STRATEGY.md`'s E2E section.

**Bug 1 — untracked `profiles_role_check` CHECK constraint**: the live
project rejected `role = 'supervisor'` even though nothing in this repo's
tracked migrations constrains that column (§25 had asserted, correctly at
the time for the *tracked* migrations, that no such constraint existed).
Something added one directly against the project outside version control.
Caught by querying the live schema table-by-table via REST before trusting
any migration-list assumption; fixed and made tracked by
`phase26_role_check_constraint.sql`. **Lesson generalized**: never assume
a live project's schema matches the migration files without checking —
this project turned out to be ten migrations behind (stuck since before
`phase16`) in addition to this one untracked addition.

**Bug 2 — `ASHAPanel.jsx` crashed on `My Submissions` for any real ASHA
account with history**: `getMySubmissions()` returns the cursor-paginated
wrapper `{ cases, hasMore, nextCursor, nextId }` (documented in its own
JSDoc comment), but the panel passed the whole object to `setSubmissions`
and called `.map()` on it — a `TypeError` on every real render, caught
only by the top-level `ErrorBoundary`. Pre-existing, unrelated to the
round-3 features; a pure frontend/backend contract mismatch that no
backend pytest could ever see, and no existing frontend test exercised
this panel against a real backend response shape. Fixed: `setSubmissions
(data.cases)`.

**ES256 finding — the local-JWT-verification fast path (§1) never engages
on this specific project**: captured tokens showed `"alg":"ES256"`
(asymmetric — Supabase's newer JWT Signing Keys), not the legacy HS256
shared-secret scheme `SUPABASE_JWT_SECRET` verifies. Every request on this
project therefore falls through to `auth.py`'s network fallback
(confirmed in the request log: a `GET /auth/v1/user` call per request),
paying the ~1.5-2s round-trip §1 was specifically built to avoid. This is
not a bug — the fallback is working exactly as designed and the app is
fully correct — but it means the latency win documented in §1 is
currently theoretical for this project, not realized. **Not fixed in this
pass** (would need JWKS fetching + ES256 verification support, a real
scope increase); flagged here so it isn't mistaken for "already handled"
and re-discovered from scratch later. If this project's actual latency
becomes a problem, this is the first thing to address.

### 30. Independent Qwen Coder "Clinical AI Validation Laboratory" review — verdict, evidence, and the pregnancy-BP fix

**Context**: the user ran a separate AI system (Qwen Coder) against a
harshly adversarial red-team prompt ("Clinical AI Validation Laboratory...
mission is to find bugs, not confirm the system works... assume this system
is guilty until proven innocent") and got back a report claiming 18
"critical" safety violations, including undertriaged sepsis, non-functional
safety-net thresholds, and "temporal blindness," with a "NOT READY FOR
DEPLOYMENT" regulatory verdict. Qwen could not open a PR, so the user
handed over its output files (scripts + result JSON/CSV/txt) for
independent review rather than acting on the report at face value.

**Verdict, up front**: of the 18 reported violations, 16 are artifacts of
one broken test script (a form-data schema that doesn't match VitalNet's
real API), reproduced and confirmed below. **One is a genuine gap**,
now fixed (severe hypertension in pregnancy below the general
hypertensive-crisis threshold — see the safety-net rule added this pass).
The remaining findings are legitimate but pre-existing, honestly-scoped
limitations rather than "bugs": two are the model's own over-triage
tendency (safer direction, not fixed), and "temporal blindness" is an
accurate description of a static single-encounter classifier by design
(partially mitigated at the cross-visit level by §22, not within one
encounter).

**Root cause of the 16 false "critical" findings — a fabricated schema**:
`backend/scripts/clinical_validation_phase2.py` builds patient dicts using
field names that do not exist anywhere in VitalNet — `age`, `sex`,
`systolic_bp`, `diastolic_bp`, `respiratory_rate`, `gcs`,
`capillary_refill_time`, `consciousness`, `urine_output`, `comorbidities`
— instead of the real `IntakeForm` fields (`patient_age`, `patient_sex`,
`bp_systolic`, `bp_diastolic`, `symptoms` list, `known_conditions` free
text). VitalNet also has no `respiratory_rate`, `gcs`, `capillary_refill_time`,
or `urine_output` field at all — an ASHA worker doing basic field triage
does not compute a Glasgow Coma Scale or measure urine output; the nearest
real equivalent to "GCS 8 / unresponsive" is the `altered_consciousness`
symptom flag. The script calls `predict_triage()` directly with these raw
dicts, bypassing the Pydantic `IntakeForm` validation layer that the real
API always applies — so `form_data.get("bp_systolic")` silently returns
`None` for every one of its cases, and every BP-based safety-net rule and
model feature goes dark. Notably, **two of Qwen's own four validation
scripts** (`clinical_validation_lab.py` for Phase 1, and
`stress_test_classifier.py`) used the *correct* field names throughout and
came back clean — 3,000 cases / 0 violations and 491 cases / 0 violations
respectively — confirming the schema mismatch was specific to one script,
not a pervasive issue with Qwen's methodology or a real weakness in the
classifier.

**Reproduced, side by side** (`python -c` against the real
`predict_triage()`, both runs against the identical unmodified classifier):

| Case | Qwen's exact dict → | Same clinical intent, real field names → |
|---|---|---|
| GCS 8, "unresponsive" | ROUTINE | `symptoms=['altered_consciousness']` → **EMERGENCY** (safety net) |
| Systolic BP 79 | ROUTINE | `bp_systolic=79` → **EMERGENCY** (model's own read) |
| masked_sepsis_elderly (82F, confused, SBP 95, no fever) | ROUTINE (98.4% conf.) | `bp_systolic=95, symptoms=['altered_consciousness']` → **EMERGENCY** (safety net) |
| masked_sepsis_immunocompromised (45M, SBP 88, HR 115) | URGENT (99.4% conf.) | `bp_systolic=88` → **EMERGENCY** (model's own read) |
| preeclampsia_warning (34F, pregnant, BP 155/105, headache) | ROUTINE | `bp_systolic=155/105, symptoms=['severe_headache']`, **no** `is_pregnant` field yet → URGENT only (model's read — the real gap, see below) |

Every "masked sepsis" and boundary-condition finding flips to the
clinically-correct tier the moment the same scenario is expressed in
VitalNet's actual schema — most via the *existing* safety net or the
model's own learned judgment, needing no code change at all. These were
never live behavior; they could not occur through the real API, since
every real request is built from a validated `IntakeForm`, which by
construction only ever produces VitalNet's real field names.

**The one genuine finding — preeclampsia below the general hypertensive-crisis
threshold**: even with every field name corrected, `preeclampsia_warning`
(BP 155/105 in pregnancy, with a severe headache) only reached **URGENT**
via the model's own judgment — not EMERGENCY — because the existing
safety net's hypertensive-crisis rule requires systolic BP ≥ 180, and
155/105 is well below that. ACOG Practice Bulletin 222 puts the severe-
preeclampsia bar much lower for a pregnant patient: BP ≥ 160/110 alone, or
≥ 140/90 with a severe feature (severe headache, severe abdominal pain).
VitalNet had no structured way to know a patient was pregnant — only a
best-effort free-text keyword match in
`clinical_features.py::_pregnancy_adjustment`, which feeds the ML model's
statistical judgment but cannot back a deterministic guarantee.

**Fix applied this pass**:
1. A new `is_pregnant: Optional[bool]` field on `IntakeForm`
   (`backend/app/models/schemas.py`), a checkbox in `IntakeForm.jsx` shown
   only when `patient_sex === "female"`, and the matching Zod validation in
   `frontend/src/utils/validation.js`. Deliberately a real structured field,
   not a reuse of the existing free-text pregnancy inference — that
   inference is left exactly as-is for the ML model's own feature, since
   this new field needs to be reliable enough to gate a *deterministic*
   safety-net rule.
2. A new rule at the end of `_safety_net_check()`
   (`backend/app/ml/classifier.py`), mirrored exactly in
   `safetyNetCheck()` (`frontend/src/utils/clinicalRules.js`): when
   `is_pregnant` is set, BP ≥ 160/110 escalates to EMERGENCY unconditionally;
   BP ≥ 140/90 escalates to EMERGENCY only alongside `severe_headache` or
   `severe_abdominal_pain` (the severe features this app can actually
   observe from its symptom checklist). Verified: with the fix,
   `preeclampsia_warning`'s exact scenario now reaches **EMERGENCY**
   through the deterministic safety net, not the model's probabilistic
   read.
3. Test coverage added on both sides: three new cases in
   `backend/tests/test_classifier_safety.py` (severe BP always emergency
   regardless of symptoms; moderate BP + severe feature is emergency;
   the same BP values without `is_pregnant` do **not** trigger this rule)
   and a new `frontend/tests/safetyNet.test.mjs` giving `safetyNetCheck`/
   `news2ConcerningVital` their first direct test coverage (previously
   only exercised indirectly via `treeParity`/`featureParity`), wired into
   both CI jobs in `.github/workflows/ci.yml`.

**Deliberately not done: retraining the model.** `assign_triage_label()`
in `backend/scripts/train_classifier.py` is a separate synthetic-label
generator for training data, architecturally distinct from the
inference-time safety net. Every existing safety-net rule in this codebase
already provides its guarantee purely at inference time, independent of
the trained model's own judgment — that is the entire point of the
two-layer design (§ "safety net" throughout this file). Adding the
pregnancy rule to `_safety_net_check()`/`safetyNetCheck()` alone fully
satisfies the same guarantee with no retrain, no new export/parity risk,
and no chance of a training-data regression. Retraining to *also* teach
the model this pattern statistically would be a legitimate future
enhancement, but is a strictly larger, riskier scope than this fix requires.

**Findings deliberately left as documented limitations, not fixed here**:
- **Pediatric/geographic over-triage** — `infant_normal_vars` (6-month-old,
  HR 140, otherwise normal) and `high_altitude_resident` (chronic SpO2 88%,
  asymptomatic) both reach EMERGENCY through the *model's own* learned
  judgment once field names are corrected — not the safety net, not the
  NEWS2 floor. The model lacks age-adjusted vital-sign ranges and
  altitude-adaptation context in its synthetic training data. This is
  over-triage (the safer failure direction) rather than under-triage, and
  fixing it properly means enriching `train_classifier.py`'s synthetic
  generator with age/altitude-aware normal ranges and retraining — out of
  scope for a safety-net-only pass. Tracked here so it isn't
  re-discovered as a surprise; a candidate for the next model-retraining
  round (see `backend/app/ml/MODEL_CARD.md` limitations section).
- **"Temporal blindness"** — accurate description of the architecture, not
  a bug: `predict_triage()` classifies one encounter's snapshot vitals; it
  was never designed to detect a worsening trend within a single visit.
  The system's actual mitigation for deterioration lives at the cross-visit
  level (§22's `deterioration_alert`, comparing tier across a patient's
  visit history via the patient continuity code), which the single-call
  validation script doesn't exercise since it never supplies visit history.
  A within-visit serial-vitals trend feature would need repeated
  measurements the current `IntakeForm` doesn't collect — a real feature
  gap, but a scope decision, not a defect.

**Lesson for future third-party or AI-generated validation reports**:
verify a validation harness calls the code under test the way production
actually calls it (same schema, same entry point) before trusting a
"critical" verdict — a broken test fixture reads exactly like a real bug
until reproduced against the real interface, as the 16 false findings here
demonstrate. Phase 1 and the stress test in this same review are the
counter-example: same target code, correct field names, legitimately clean
results across 3,491 cases — proof the classifier itself was never the
problem for those findings.

### 31. Model v3.1.0 — age-aware paediatric labels, bit-exact float32 parity, and a lighter model

**Context**: a round-5 ML pass targeting three explicit goals — maximum
accuracy, the lightest possible model for decade-old hardware, and closing
the documented infant over-triage limitation (§30 / MODEL_CARD). All three
were achieved together; the model shrank while the paediatric limitation was
fixed and calibration held.

**Root cause of the infant over-triage (a label bug, not just data
sparsity)**: `train_classifier.py`'s synthetic-label scorer age-adjusted
heart rate (`_pediatric_hr_score`) and temperature (`_pediatric_temp_score`)
but scored systolic BP with adult bands (`_bp_sys_score`) at every age. A
6-month-old's perfectly normal systolic BP (~85) is "hypotensive" by adult
bands, so the scorer stamped a healthy infant's *label* EMERGENCY, and the
model faithfully learned it. Confirmed by direct probe: `shock_index`
(HR/SBP) for that infant is 1.65 (adult "shock" > ~0.9) and
`hemodynamic_instability` 10.0 — the feature engineering is adult-anchored
too. Infants were also only ~1.7% of the exponential-age training draw, so
the model had few counter-examples.

**Fix (all in `train_classifier.py`, the training-time scorer/generator —
the trained artifacts change, no inference-code or JS feature-engineering
change)**:
1. `_pediatric_bp_score(age, bp_sys)` — age-banded systolic-BP scoring using
   the standard PALS 5th-percentile hypotension thresholds (neonate <60,
   infant <70, child <70+2·age), routed in `news2_like_score` for age<18.
2. Age-gated the qSOFA hypotension criterion (SBP≤100 is normal for a young
   child; only applied at age≥12).
3. Age-appropriate BP *generation* — `_correlated_vitals` now anchors a
   child's baseline systolic BP to ~85+2·age instead of the adult ~118, so
   the generator emits physiologically real infants and the model actually
   sees the normal-low-BP-infant pattern.
4. ~22% paediatric oversampling (`_sample_age`, `PEDIATRIC_FRACTION`), skewed
   to under-2s where adult bands are most wrong.

Result: the exact 6-month-old case (HR 140, BP 85/55, all normal) now
classifies **URGENT** (the conservative NEWS2 floor — mild, safe over-triage
that stays documented and unchanged) instead of **EMERGENCY**, while
genuinely sick children (frank hypotension for age, SpO2 84, neonatal fever)
still escalate correctly. The deterministic layers were deliberately left
adult-tuned and untouched — they must stay dead-simple and JS-mirrored, and
their residual URGENT flooring is the safe direction.

**Bit-exact float32 parity (a genuine hardening of the safety-critical
online/offline agreement)**: the retrain surfaced a latent parity bug. The
offline JS tree evaluator and its Python reference (`tree_export.py`) compared
`x <= threshold` in float64 against a threshold decimal-rounded to 9 places,
while the server casts features to `np.float32` before `predict`. A feature
value landing exactly on a split threshold (common for low-cardinality
discrete features) could therefore take a different branch offline vs online —
2 of 5,400 held-out samples diverged (adjacent tiers, at genuine model
boundaries, but a real divergence). The old model passed only by luck. **Fix**:
both evaluators now cast *both* operands to float32 in the comparison
(`np.float32(...)` / `Math.fround(...)`), which snaps the rounded threshold
back to the identical float32 the server used — making
sklearn == onnx == tree-JSON == JS bit-identical. Verified: 0 disagreements
across the full held-out set, and `treeEvaluator.js` remains a 1:1 mirror of
the reference. The 9-decimal JSON rounding is kept (compactness) since the
float32 cast makes it lossless for the comparison.

**Efficiency (the "lightest possible" goal)**: `max_leaf_nodes=24` (from the
default 31) plus a faster learning rate (0.09) with tighter early-stopping
patience (18) converge in fewer boosting iterations. The shipped
`triage_trees.json` — the artifact a 2 GB phone downloads and parses offline
— dropped from **1,236 KB / 747 trees to 934 KB / 702 trees (~24% smaller)**
with no loss of accuracy. EMERGENCY class weight was nudged 6→7 to protect
emergency recall against the shorter fit.

**Metrics (v3.1.0, held-out balanced test / 5-fold CV / realistic
prevalence)**: ~98.7% / 98.6% accuracy, CV EMERGENCY recall 0.985, ECE 0.003
(balanced) / 0.009 (realistic-prevalence), realistic-prevalence accuracy
~99.3%. The handful of model-level EMERGENCY misses are adjacent-tier
(EMERGENCY→URGENT) or caught at inference by the safety net / NEWS2 floor —
the two-layer guarantee is unchanged. Full numbers regenerate into
`MODEL_CARD.md` / `CLASSIFIER_CHANGELOG.md` on every training run.

**Deliberately not done**: an altitude / `baseline_spo2` field (the remaining
over-triage limitation is unresolvable without it, and treating isolated
SpO2 88 as concerning is the safe default); age-in-months intake capture
(specced as FEATURES_ROADMAP §4.1 — the model now understands fractional
infant age, but the integer-year intake field can't yet supply it precisely).

### 32. A fourth branch, `experimental`, for major reforms — kept out of the `dev`/`main`/`test` pipeline entirely

**Context**: a full TypeScript migration + rules-first triage rearchitecture
began (a multi-week, multi-phase rewrite: a new `clinical-core` package
replacing four hand-mirrored Python/JS clinical-logic pairs, `SECURITY
DEFINER` Postgres functions replacing app-layer `supabase_admin` discipline,
and a new Deno/Hono edge-function backend alongside the existing FastAPI
one). The first several phases were built on a short-lived branch off `dev`
(`feature/ts-clinical-core`), following this repo's normal feature-branch
convention (§9) — but that convention assumes a feature branch merges back
into `dev` in days, not weeks, and §9's three-branch model exists
specifically to keep `main`/`dev`/`test` reliable for building, testing, and
deploying *already-shipped* functionality. A multi-week rewrite left
mid-flight in an intermediate, sometimes-broken state doesn't belong
anywhere near that pipeline, even temporarily.

**Decision**: `experimental` is a fourth long-lived branch, independent of
`main`/`dev`/`test`, reserved for this class of work — large architectural
reforms expected to span many commits with an intermediate broken state,
not incremental features. It is not created off `dev` as a short-lived
branch and is not merged back automatically; `dev`/`main`/`test` remain
solely for the existing, shipped codebase. Promotion happens deliberately:
once a reform phase (or the whole reform) is complete and independently
verified, it's proposed to `dev` via a normal reviewed PR — the same bar as
any other change, not a fast-tracked merge just because the branch is
long-lived. `feature/ts-clinical-core`'s six phase commits (Phase 0–3
foundation: monorepo scaffolding, `clinical-core`, DB `SECURITY DEFINER`
functions + CI drift detection, and the first Tranche-A edge-function
endpoints) moved to `experimental` unchanged — the branch was recreated
pointing at the same history, not rebuilt.

**Consequences**: `dev` stays exactly what §9 intended it to be — the
active-development line for everything already shipped — even while a
large rewrite is in progress elsewhere. CI on `experimental` (the new
`db-schema-drift.yml` and `api-edge-function.yml` workflows) runs
independently and never gates `dev`/`main`/`test`. The tradeoff: a second
long-lived branch is more to keep track of than the previous exactly-three
model, and it must not become a dumping ground for anything someone would
rather not put through normal review — it is specifically for reforms of
this scale, not a general-purpose "experiments" branch.

### 33. Round 6 rebuild — TypeScript migration, rules-first triage, unified outbox, DB discipline: what, why, evidence, rollback

**Context**: four clinical-logic pairs were hand-mirrored across Python
(the FastAPI backend) and JavaScript (the browser, for offline triage) —
Pydantic↔Zod validation, `_safety_net_check`↔`safetyNetCheck`,
`ClinicalFeatureEngineer`↔`buildFeatureMap`, and a contraindications table
— plus a whole parity-test apparatus (four suites, golden vectors, CI jobs)
whose only job was catching drift between the copies. Three further
problems compounded it: the ML model was trained on its own scorer's
labels (a circular validation of sorts) yet sat in the *authoritative*
triage path in production, with the deterministic safety net only as a
backstop around it; the offline layer was a set of feature-specific
IndexedDB queues rather than one generic outbox with server-side dedup; and
DB privilege boundaries lived in app-layer discipline (`supabase_admin`
"narrow exceptions," §29) rather than the database itself. This entry
records the six-phase rebuild (`experimental` branch, §32) that addressed
all four, what changed, the evidence it didn't silently change clinical
behaviour where it shouldn't have, and exactly what's still gated before
any of it touches production traffic.

**Decision**: build a pnpm workspace monorepo alongside the existing
`backend/`, strangler-fig style — every phase lands green and shippable,
the legacy backend stays fully deployable throughout, and nothing is
deleted until its replacement is validated.

1. **One language for clinical logic.** `packages/clinical-core`
   (TypeScript) is now the single source of truth: the Zod intake schema
   (merging `schemas.py`'s bounds with the old `validation.js`), the
   deterministic rules engine (bands + overrides + citations), 43-feature
   engineering, an offline tree evaluator with Saabas-style path
   attribution, and contraindication checks. Both `apps/web` (browser,
   offline) and `apps/api` (server, online) import it directly — there is
   no second copy to drift out of sync, and the four apps/web-side parity
   test suites that used to guard against that drift are deleted (their job
   is now structurally impossible to fail at, not just tested for).
2. **Rules-first triage: the model becomes advisory.** The rules engine
   (promoted from `train_classifier.py`'s v3.1.0 age-aware training-label
   scorer, previously training-only code) is now the sole authority over
   `triage_level`. The model's own tier, confidence, and low-confidence
   flag are persisted and shown as a *suggestion* — it drives queue
   prioritization and a documented model-promotion gate (comparing
   `model_tier` against outcomes/overrides), but never the tier itself.
   Model/rules disagreement (`model_agreed === false`) folds into
   `needs_review` server-side, so an EMERGENCY(model)→lower(rules)
   de-escalation can never silently sink out of the priority queue
   unflagged — the rules engine is never "low confidence" about its own
   decision the way a probabilistic model can be. Saabas path attribution
   (`treeEvaluator.ts`) replaces SHAP at inference for the advisory
   model's `top_factors`; `shap` remains a training-only dependency for
   artifacts no longer shipped.
3. **A unified offline outbox.** `apps/web/src/lib/outbox.js` replaces the
   case-submission-specific `offlineQueue.js` with a generic IndexedDB
   event queue (`{event_id, type, payload, created_at, attempts, status,
   last_error}`). `event_id` is the *same* uuid as `case_records.client_id`
   and the `X-Event-Id` header `apps/api`'s new idempotency middleware
   dedupes on — one idempotency key end-to-end instead of three
   independently-generated ones. A permanently-failing (4xx) event is
   dead-lettered, not silently dropped, and surfaced in `OfflineBanner.jsx`
   with retry/discard actions. Doctor actions stay online-only for now;
   the store itself is generic enough that a future offline-capable action
   doesn't need another IndexedDB version bump.
4. **DB discipline moves into the database.** `phase28_security_definer_fns.sql`
   replaces four narrow `supabase_admin` aggregate-query exceptions
   (§29's "retired narrow aggregate exception") with `SECURITY DEFINER`
   Postgres functions (`fn_deterioration_count`, `fn_open_case_counts`,
   `fn_team_metrics`, `fn_outbreak_signal_counts`, `fn_rate_limit`,
   `fn_schema_fingerprint`) — internal role checks via `auth.uid()`, `REVOKE
   ALL` + `GRANT EXECUTE TO authenticated`, so service-role usage stays
   confined to `/api/admin` + audit writes, the invariant §29 already
   claimed but hadn't fully enforced. `phase29`/`phase31` add `client_events`
   (outbox dedup) and `fn_client_event_record` (a second `SECURITY DEFINER`
   function, since `client_events` has no INSERT policy — it derives
   `submitted_by` from `auth.uid()` internally, so spoofing it is
   structurally impossible, not just policy-forbidden). A new CI job,
   `db-schema-drift.yml`, replays every tracked migration against a fresh
   Postgres on each PR and diffs the result against a committed schema
   snapshot, plus a weekly live-fingerprint check via
   `fn_schema_fingerprint()` — catching both "a migration is wrong" and "the
   live dashboard drifted outside any tracked migration" (the failure mode
   that caused the ten-migrations-behind incident in §29).
5. **A new backend, not a rewrite of the old one.** `apps/api` is a single
   Supabase Edge Function (Deno + Hono) implementing the full route surface
   in `rules_first` mode, built and tested green in CI
   (`api-edge-function.yml`) — but **not yet receiving production traffic**.
   `apps/web/src/api/base.js`'s `ENDPOINT_BACKEND` map resolves every
   endpoint to `'legacy'` today; flipping one entry to `'edge'` is the
   entire per-tranche cutover, and reverting it is the entire rollback.

**Conformance evidence** (not trusted by inspection — verified):
`tools/training/export_conformance_patients.py` generated 10,000 synthetic
patients and ran Python's pre-migration `predict_triage` (safety net →
model → NEWS2 floor) against clinical-core's `triage()` in `hybrid` mode
(the same order, reproducing the legacy semantics exactly) —
**10,000/10,000 (100.000%) agreement, zero mismatches**
(`packages/clinical-core/test/conformance/report.md`, asserted by
`hybrid.conformance.test.ts` in CI). This is the proof the TypeScript port
changed nothing before `rules_first` ever shipped. The *separate*,
informational delta — the same 10,000 patients replayed in `rules_first`
mode instead — shows **88/10,000 (0.88%) changed**: 35 upgraded to a
higher tier, 53 downgraded. Of the downgrades, **51 are
EMERGENCY(legacy)→URGENT(rules_first)**. This is not a bug: it is the
intended, quantified behavioural delta of making the rules engine
authoritative instead of the model (the model, trained on the same rules
engine's own historical labels, drifts from them slightly on borderline
cases, especially where it learned patterns the deterministic scorer's
exact boundaries don't capture). It is exactly the number a clinician
reviewer needs before `rules_first` reaches production — see the Phase 7
sign-off gate (`docs/CLINICAL_REVIEW.md`, `CODEOWNERS` on
`packages/clinical-core/src/rules/**`). The phase28/29/31 SQL migrations
were separately verified empirically against a real local Postgres 16
instance (RLS scoping, idempotent insert, unspoofable `submitted_by`,
insert-denied-without-the-function), not by inspection alone.

**Rollback map**: per-tranche, one line in `ENDPOINT_BACKEND` — verified
against a live E2E run before flipping, per §29's methodology, before
watching audit logs/metrics. `backend/app/` and
`.github/workflows/backend-keepalive.yml` are **deliberately not deleted**
as part of this rebuild — deletion is deferred until `apps/api` has
actually taken production traffic and been verified for real, not on the
strength of its test suite alone (the JWKS/ES256 auth path and the webpush
VAPID crypto have zero live-network coverage by design — see
`apps/api/README.md`'s status section and `test/auth.test.ts`'s header).
Training rewired last: `tools/training/train_classifier.py` (moved from
`backend/scripts/`) now pipes synthetic patients through
`packages/clinical-core/cli.mjs` for both labeling and feature engineering
instead of maintaining a ~190-line Python port of the same scorer — the
last hand-mirrored pair, eliminated once the TypeScript rules engine it
would have mirrored was itself verified against the legacy production path
above.

**Consequences**: online and offline triage cannot silently diverge any
more — there is one rules-engine *implementation*, not two kept in sync by
hand, and the four parity-test suites that existed only to catch that
class of bug are gone because the bug class is gone. Same implementation
does not mean same *mode*, though, and that distinction mattered in
practice — see the correction immediately below. The tradeoff this entry
exists to make explicit: `rules_first`'s 51 EMERGENCY→URGENT downgrades
are a real, quantified change in clinical behaviour, not a regression to
wave through — it does not ship to production until a named clinician has
reviewed the delta and the rules tables it comes from (Phase 7). Until
`apps/api` cuts over, `backend/`'s hybrid (model-primary) behaviour
remains what patients actually experience, and this document,
`backend/app/ml/README.md`, and `backend/app/ml/MODEL_CARD.md` describe it
accurately as the live system — not as a legacy curiosity.

**Correction, found in PR review before merge**: the first version of this
migration's `apps/web` offline triage (`utils/triageClassifier.js`)
hardcoded `mode: 'rules_first'` unconditionally, with no gate. That meant
an offline ASHA worker could see a `rules_first`-computed preliminary
tier — including, in principle, one of the 51 EMERGENCY→URGENT
cases above — *before* this entry's own sign-off gate had cleared, and
before the server itself had cut over to `rules_first`. The persisted,
authoritative record was never at risk (the outbox enqueues the raw form,
never the locally-computed tier — see Phase 5's outbox design above — so
`/api/submit` always retriages from scratch on sync), but the preliminary
*display* could disagree with what the case became once synced, which is
exactly the kind of quietly-shipped clinical-behaviour change this whole
entry argues against doing without sign-off. Fixed in the same PR:
`triageClassifier.js` now calls `triage()` in `hybrid` mode — matching
`backend/app/`'s actual live semantics — and falls back to an
override-only safety-net check (never a guessed tier) when the model
can't be loaded offline, rather than silently computing a `rules_first`
tier without one. `apps/web` moves to `rules_first` only alongside the
real `apps/api` cutover, not before it. See `apps/web/README.md`'s
"Triage logic lives in one place" section for the corrected design.
