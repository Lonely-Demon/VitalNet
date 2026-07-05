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
