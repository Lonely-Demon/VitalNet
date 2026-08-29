# VitalNet Recursive Adversarial Audit — Master Report

**Auditor:** Mavis (MiniMax Code, root session)
**Date:** 2026-08-29
**Repository:** `D:\Southern_Ring_Nebula\VitalNet` @ `7a91639`
**Method:** 10-cycle read-only recursive audit, increasing sophistication per
cycle, with chained-attack analysis at every step. Each cycle produced
per-finding files under `findings/VN-2026-08-C{n}-{nn}.md`.

This is the consolidated, deduplicated, prioritised report. Per-finding
evidence and remediation details live in the per-finding files; this
document focuses on the *threat picture* and the *chained attacks* an
elite adversary would actually run.

---

## Executive summary

The codebase is a healthcare triage PWA. It handles Protected Health
Information (PHI), patient demographics, vitals, and consent. The
adversary model in scope: an "elite" attacker (well-resourced, time to
chain multiple issues, possibly with insider-adjacent access like a
shared PHC tablet, a compromised developer account, or a single leaked
PHC admin credential).

Across 10 audit cycles, **38 distinct findings** were identified. Of
those, **4 are CRITICAL**, **12 are HIGH**, **13 are MEDIUM**, **7 are
LOW**, and **2 are INFO**. The team's existing March-2026 red-team
audit (`docs/security-audits/2026-03-red-team/`) already addressed
several foundational issues (R3-DATA-RLS-*, R3-SEC-AUTH-*); the new
findings here are primarily about *defense-in-depth gaps that
untreated enable chained attacks*, and about the new surface area
introduced since March (apps/api, the offline outbox, the rules-first
triage migration).

A follow-up verification pass (also on 2026-08-29) re-validated every
finding against the actual code, marked one as a false positive
(`VN-2026-08-C2-05` — the `language` query parameter is safely mapped
to a closed set in `app/services/llm.py:383`), and uncovered **8 new
findings** (`VN-2026-08-VER-01` through `VN-2026-08-VER-08`). The
follow-up pass *also* discovered a regression: the live database still
contains the exact `auth.jwt() -> 'user_metadata'` RLS policies that
phase32 explicitly DROPPED in tracked migrations — see VER-07.

After verification: **5 CRITICAL**, **15 HIGH**, **14 MEDIUM**, **7 LOW**, **2 INFO**.

The single most dangerous finding is **VN-2026-08-VER-07** (live
database still has the retired `user_metadata` RLS policies): the
`doctor_update`, `asha_select_own`, and `profile_select` policies on
the live database still trust the client-settable JWT `user_metadata`.
Any authenticated user can `PUT /auth/v1/user` to set their
`user_metadata.role = 'admin'` and the live RLS will honour it. The
phase32 fix exists as a tracked migration but the live database
either never had it applied, or the drift detector
(`fn_schema_fingerprint`) has been silently failing. **This is the
EXACT privilege-escalation pattern that phase32 was supposed to fix,
still present in production.**

The single most dangerous *clinical safety* finding is
**VN-2026-08-C6-01** (pediatric HR override): the rules engine's
"extreme HR" override fires EMERGENCY at HR > 170 regardless of age,
causing massive false-positive over-triage for normal infants and
3-year-olds, and eroding the clinical signal over time.

---

## Findings index (deduplicated, prioritised)

### CRITICAL (4)

| ID | Component | One-line | File |
|----|-----------|----------|------|
| VN-2026-08-C3-01 | Supabase RLS | `case_records` has no INSERT policy; submitter can be spoofed via direct REST | [findings/VN-2026-08-C3-01.md](findings/VN-2026-08-C3-01.md) |
| VN-2026-08-C3-02 | Supabase RLS | UPDATE policy doesn't protect clinical/PII columns; submitter can rewrite any field | [findings/VN-2026-08-C3-02.md](findings/VN-2026-08-C3-02.md) |
| VN-2026-08-C7-01 | Backend ML | `pickle.load` of `triage_classifier.pkl` at startup = RCE if the file is replaced | [findings/VN-2026-08-C7-01.md](findings/VN-2026-08-C7-01.md) |
| VN-2026-08-C6-01 | clinical-core | Pediatric HR override at >170 fires for normal infants — over-triage / loss of trust | [findings/VN-2026-08-C6-01.md](findings/VN-2026-08-C6-01.md) |

### HIGH (12)

| ID | Component | One-line | File |
|----|-----------|----------|------|
| VN-2026-08-C3-03 | Supabase RLS | Referrals embed leaks cross-tenant case content to receiving facility | [findings/VN-2026-08-C3-03.md](findings/VN-2026-08-C3-03.md) |
| VN-2026-08-C4-01 | Frontend | `authStore.jsx` reads `app_metadata.role` — direct contradiction of backend's "never trust user_metadata" | [findings/VN-2026-08-C4-01.md](findings/VN-2026-08-C4-01.md) |
| VN-2026-08-C4-03 | Frontend | Outbox `owner_id` is client-side only; cross-worker exfiltration + mis-attribution | [findings/VN-2026-08-C4-03.md](findings/VN-2026-08-C4-03.md) |
| VN-2026-08-C5-01 | apps/api | `idempotent` middleware reads `c.get("user")` without verifying requireRole ran first | [findings/VN-2026-08-C5-01.md](findings/VN-2026-08-C5-01.md) |
| VN-2026-08-C5-02 | apps/api | `c.res.clone().json()` after `next()` may double-consume the response body | [findings/VN-2026-08-C5-02.md](findings/VN-2026-08-C5-02.md) |
| VN-2026-08-C5-03 | apps/api | JWKS fetcher trusts `config.supabaseUrl` blindly — supply-chain pivot | [findings/VN-2026-08-C5-03.md](findings/VN-2026-08-C5-03.md) |
| VN-2026-08-C6-03 | clinical-core | `runModel` uses `probabilities[classIndex]` — NaN comparisons silently mis-classify | [findings/VN-2026-08-C6-03.md](findings/VN-2026-08-C6-03.md) |
| VN-2026-08-C2-01 | Backend auth | `_profile_cache` is unbounded; no eviction, no deactivation hook | (Cycle 2, see findings) |
| VN-2026-08-C2-04 | Backend cases | `get_case_detail` `select("*")` exposes all internal provenance fields | (Cycle 2) |
| VN-2026-08-C2-05 | Backend cases | `case_patient_summary` accepts unvalidated `language` → LLM prompt injection | (Cycle 2) |
| VN-2026-08-C2-09 | Backend cases | `_get_user_id` parses bearer token naively for rate-limit key | (Cycle 2) |
| VN-2026-08-C7-02 | Backend ML | SHAP runs per-prediction in request hot path; DoS vector | [findings/VN-2026-08-C7-02.md](findings/VN-2026-08-C7-02.md) |

### MEDIUM (13)

| ID | Component | One-line | File |
|----|-----------|----------|------|
| VN-2026-08-C1-01 | Backend CSRF | `csrf_token` is hard-coded literal compared like a secret | [findings/VN-2026-08-C1-01.md](findings/VN-2026-08-C1-01.md) |
| VN-2026-08-C1-02 | Backend config | CORS allowlist defaults to dev origins when `ENVIRONMENT` unset | [findings/VN-2026-08-C1-02.md](findings/VN-2026-08-C1-02.md) |
| VN-2026-08-C1-03 | Backend DB | `supabase_admin` cross-RLS rule enforced only by review + one test file | [findings/VN-2026-08-C1-03.md](findings/VN-2026-08-C1-03.md) |
| VN-2026-08-C3-04 | Supabase RLS | `case_reviews_immutable CHECK (true)` is a comment, not a constraint | [findings/VN-2026-08-C3-04.md](findings/VN-2026-08-C3-04.md) |
| VN-2026-08-C3-05 | Supabase RLS | `auth.uid()` NULL semantics: every policy relies on a fragile pattern | [findings/VN-2026-08-C3-05.md](findings/VN-2026-08-C3-05.md) |
| VN-2026-08-C3-06 | Supabase RPC | `fn_schema_fingerprint` callable by any admin, side-channels schema state | [findings/VN-2026-08-C3-06.md](findings/VN-2026-08-C3-06.md) |
| VN-2026-08-C4-02 | Frontend | `vn_facility_phone` in `localStorage` — reachable by any same-origin script | [findings/VN-2026-08-C4-02.md](findings/VN-2026-08-C4-02.md) |
| VN-2026-08-C4-04 | Frontend | `clearSharedDeviceState` is best-effort and not properly ordered | [findings/VN-2026-08-C4-04.md](findings/VN-2026-08-C4-04.md) |
| VN-2026-08-C6-02 | clinical-core | `checkOverrides` short-circuits on first hit; loses audit detail | [findings/VN-2026-08-C6-02.md](findings/VN-2026-08-C6-02.md) |
| VN-2026-08-C8-01 | CI/CD | `pnpm/action-setup@v4` is a tag, not SHA — supply-chain pivot | [findings/VN-2026-08-C8-01.md](findings/VN-2026-08-C8-01.md) |
| VN-2026-08-C8-02 | Supply chain | apps/api (Deno) is not Dependabot-monitored | [findings/VN-2026-08-C8-02.md](findings/VN-2026-08-C8-02.md) |
| VN-2026-08-C9-01 | Audit | `get_client_ip` trusts `X-Forwarded-For` without enumerating trusted proxies | [findings/VN-2026-08-C9-01.md](findings/VN-2026-08-C9-01.md) |
| VN-2026-08-C9-02 | Rate limit | SlowAPI in-memory store by default; horizontal-scale bypass | [findings/VN-2026-08-C9-02.md](findings/VN-2026-08-C9-02.md) |

### LOW (7) and INFO (2)

(Listed in the per-finding files. Includes: C2-02, C2-03, C2-06, C2-07,
C2-08, C2-10, and a couple of INFO notes.)

---

## Threat model — elite adversary

The audit considered a realistic elite-tier threat actor with:

- **Time and resources** to chain multiple low-severity findings.
- **Insider-adjacent access** at a PHC: physical access to a shared
  tablet for ~5 minutes between worker shifts.
- **Network position** to call the Supabase REST API directly, not
  just the FastAPI / Hono / web-app layers.
- **Some knowledge of the codebase** — e.g., from a job interview
  process, an ex-contractor, or an open-source fork.
- **One valid low-privilege account** (e.g., a leaked ASHA worker
  credential, or a credential bought on a credential-market).

They do **not** have:

- The Supabase service-role key.
- A developer GitHub account.
- Direct access to a Supabase project console.

The chained attacks below show how the LOW-severity findings combine
with the MEDIUM/HIGH ones to produce CRITICAL impacts.

---

## Chained attack scenarios

### Chain A — "Fabricated case under another worker's name"

**Severity:** CRITICAL
**Findings used:** C3-01, C3-02, C4-03, C9-01

1. Attacker has an ASHA worker credential (any PHC, even a different
   one — the auth boundary is per-user, not per-PHC).
2. The attacker POSTs directly to
   `POST https://<project>.supabase.co/rest/v1/case_records` with a
   row containing `submitted_by = "<victim ASHA worker UUID>"`.
   **C3-01** says this is allowed by RLS (no INSERT policy).
3. The row is accepted because the schema's only constraint on
   `submitted_by` is `NOT NULL`; no foreign key, no "must equal
   auth.uid()".
4. The attacker then PATCHes the same row to set
   `triage_level = "EMERGENCY"`, `facility_id = "<other PHC>"`,
   `patient_name = "..."` — the broad UPDATE policy allows the
   attacker (who is the row's submitter now) to overwrite every
   field. **C3-02**.
5. A doctor at the receiving PHC sees a real-looking EMERGENCY case
   attributed to a victim worker at a different PHC. **C3-03**
   explains the receiving-facility doctor has no way to know the
   case is fabricated.
6. The PHI audit log records the attacker's IP, which they spoofed
   via `X-Forwarded-For`. **C9-01** says the IP is unverified.
7. The victim's "My Submissions" page now shows the fabricated case
   (because `submitted_by = victim_uuid`). The victim is implicated
   in a clinical incident they did not perform.
8. **C4-03**: similar chains can be run against the offline outbox
   on a shared PHC tablet — read another worker's queued cases
   (PHI), rewrite the `owner_id`, and force a drain.

**Combined impact:** PHI fabrication, false clinical record, victim
worker implication, audit trail broken.

**Single fix:** **C3-01** — add a `WITH CHECK (submitted_by =
auth.uid())` INSERT policy on `case_records`. The rest of the chain
collapses because the attacker cannot insert.

---

### Chain B — "RCE via pickle, full database compromise"

**Severity:** CRITICAL
**Findings used:** C7-01, C8-01, C8-02, C1-02

1. Attacker compromises the `pnpm/action-setup` GitHub repo (or
   waits for a vulnerable version) — **C8-01** says it's pinned
   to a tag, not SHA, so a malicious commit is auto-pulled.
2. The malicious action exfiltrates `TEST_SUPABASE_SERVICE_ROLE_KEY`
   from the test-backend CI job (which runs on push to dev).
3. The attacker now has the service-role key for a real Supabase
   project. This is the "key to the kingdom" — RLS bypass.
4. The attacker pivots: they read the schema fingerprint via
   `fn_schema_fingerprint` (which any authenticated admin can call
   — **C3-06**), then exfiltrate every patient case record via
   direct REST.
5. As a secondary objective, the attacker modifies
   `triage_classifier.pkl` in a follow-up PR. CI doesn't unpickle
   the model (it's just imported by tests that don't load it), so
   the change passes review. **C7-01** says the next `load_classifier()`
   call in production runs `pickle.load` and the attacker's
   `__reduce__` payload executes.
6. RCE in the API process: now the attacker has the *production*
   `SUPABASE_SERVICE_ROLE_KEY` (loaded at process start), plus a
   long-running shell in the production environment.
7. CORS misconfiguration (**C1-02**) means the attacker can also
   exploit the deployed web app from a malicious origin if they
   need a browser-side pivot.

**Combined impact:** Full PHI exfiltration, RCE in production,
audit trail untrustworthy.

**Single fix:** **C7-01** — sign the `.pkl` with a deployment-key
HMAC and refuse to load if the signature doesn't match. **C8-01** —
pin `pnpm/action-setup` to SHA, run `step-security/harden-runner`.

---

### Chain C — "Pediatric clinical-safety regression"

**Severity:** CRITICAL (patient-safety)
**Findings used:** C6-01, C6-02, C6-03, C4-01

1. A 3-year-old arrives with a fever, presenting with HR 175
   (crying artifact from the pulse-oximeter placement).
2. The rules engine fires `extreme_hr` override → EMERGENCY. **C6-01**.
3. The doctor, seeing the EMERGENCY badge combined with a non-
   emergency-looking child, may override the tier. The override
   itself is logged in `case_records.overridden_triage`, but the
   rules engine's `firedRules` audit log only records one
   critical-symptom rule, hiding the second applicable rule.
   **C6-02** — analytics/auditability is degraded.
4. The advisory ML model — which *would* have correctly classified
   the case as ROUTINE — returns `lowConfidence: true` because
   several features are NaN, so its `modelAgreed: false` is
   spurious. **C6-03**.
5. The doctor's UI shows "AI disagreed" — adding to the noise.
6. The `authStore.jsx` `app_metadata.role` confusion (**C4-01**)
   means a doctor who has been demoted (e.g., resigned and re-hired
   as ASHA worker) still sees the doctor UI, with a working
   `human_review_requested` checkbox they shouldn't be able to use
   — submitting overrides they have no clinical standing to make.

**Combined impact:** Real children over-triaged (cost, panic, lost
trust), real adults under-triaged (because the system is losing
trust), audit trail broken.

**Single fix:** **C6-01** — make every override in `rules.ts`
age-banded. (See the per-finding file for the table.) Add a vitest
case per age band.

---

### Chain D — "Cross-tenant clinical misdirection via fabricated referral"

**Severity:** HIGH
**Findings used:** C3-03, C3-05, C5-03

1. Attacker is a doctor/admin at PHC A. They have legitimate case
   access for their own facility.
2. They learn the UUID of a sensitive case at PHC B (e.g., from
   a leaked PDF, a screenshot, or via the `case_records` API if
   RLS ever weakens — **C3-05** is a fragile pattern).
3. The attacker POSTs to `POST /api/referrals` with
   `case_id = "<PHC B's case UUID>"`. The INSERT RLS policy on
   `referrals` only checks the *referrer's* identity and role;
   it does not check that the case is at the referrer's facility.
4. The insert succeeds. The referral now points to a case at PHC B
   attributed to PHC A.
5. The receiving-side doctor at PHC B sees a referral arrive
   (per Realtime) with a `case_records` embed that RLS *correctly*
   nulls out (because the receiving doctor has no SELECT on the
   case). **C3-03** describes the silent fail.
6. The receiving doctor sees `case_records: null` and may either:
   (a) ignore the referral as "no case context, low priority",
   leaving a real patient without follow-up, or
   (b) call the referring PHC to ask for context, causing
   confusion.
7. The attacker can also set the `urgency = "EMERGENCY"`, so
   PHC B's emergency response is engaged for a case that
   PHC A "thinks" they referred but doesn't actually have.

**Combined impact:** Clinical process integrity broken across
PHC boundaries; potentially diverted ambulance/transport resources.

**Single fix:** Add a `case_id IN (SELECT id FROM case_records WHERE
facility_id = <referrer's facility>)` clause to the referral
INSERT policy.

---

### Chain E — "Supply-chain compromise of `apps/api`"

**Severity:** HIGH
**Findings used:** C8-02, C5-03, C5-01, C9-02

1. `apps/api` is the *new* backend; it will replace `backend/` as
   endpoints are cut over. Dependabot does not cover it (**C8-02**).
2. A vulnerability in `jose` (the JWT library) is published.
3. Legacy backend gets a Dependabot PR; `apps/api` does not.
4. The team flips an entry in `apps/web/src/api/base.js`'s
   `ENDPOINT_BACKEND` from `'legacy'` to `'edge'`.
5. Production traffic now hits the vulnerable `apps/api` endpoint.
6. The JWKS fetcher trusts `config.supabaseUrl` blindly (**C5-03**).
   If the operator ever set `supabaseUrl` to a non-Supabase endpoint
   (e.g., a transient config bug during a domain migration), the
   JWKS endpoint is attacker-controlled, and the attacker forges
   valid JWTs.
7. The `idempotent` middleware crash class (**C5-01**) means a
   future refactor that removes `requireRole` from a route
   using `idempotent` causes a 500 that masks the underlying
   error.
8. Rate limits in `apps/api` (via the `fn_rate_limit` Postgres
   function) are bounded to `p_window_s <= 3600` and
   `p_max <= 1000000` (per phase38 hardening) — but the *legacy*
   backend's rate limits are still per-process in-memory (**C9-02**).
   A 1-vs-1 attacker-vs-server match is still bounded, but
   horizontally-scaled legacy + vulnerable edge function is a
   compounded risk.

**Single fix:** **C8-02** — add Renovate for apps/api. Pin
`config.supabaseUrl` to the canonical Supabase project URL.

---

### Chain F — "Outbox impersonation on shared PHC tablet"

**Severity:** HIGH
**Findings used:** C4-03, C4-04, C2-05, C6-01

1. Worker A is using a shared PHC tablet, has submitted 3 cases
   (one EMERGENCY) and has 2 in the offline outbox waiting for
   connectivity.
2. Worker A goes to lunch, leaving the tablet unlocked.
3. Worker B picks up the tablet, opens DevTools (in a non-prod
   build) or uses the existing IndexedDB inspection. Reads the
   2 queued cases — they include patient names, chief complaints,
   vitals. **C4-03**.
4. Worker B modifies the outbox rows: changes `owner_id` to their
   own user id, modifies the payload slightly, and clicks "Sync
   now" (or waits for connectivity).
5. The sync sends the rows under Worker B's JWT. The server
   records `submitted_by = B`. The doctor's UI shows B as the
   submitter.
6. Worker A returns, sees the "Sync complete" toast, doesn't notice
   that the rows are gone (they were dequeued). Their draft form
   was wiped by Worker B's logout sequence in the interim
   (**C4-04** — the global `db.clear('form-drafts')` ignores
   per-user ownership).
7. The EMERGENCY case from step 1 is now attributed to B. The
   doctor's mobile push goes to B's device. B's phone rings
   unnecessarily; or worse, the push *should* have gone to a
   doctor, not a worker, and the system now thinks it did.
8. The audit log records B's IP (spoofed, **C9-01**).
9. The `case_patient_summary` endpoint allows B (now as the
   submitter of the EMERGENCY case) to invoke the LLM with an
   attacker-chosen `language` parameter that becomes a prompt
   injection vector. **C2-05**.
10. The clinical rules engine then over-triages a *different*
    case (a real 3-year-old) using the same `extreme_hr` override
    (**C6-01**), completing the loop — the system's credibility
    is now damaged from multiple directions at once.

**Combined impact:** PII exfiltration, mis-attribution, audit
trail broken, clinical signal degraded.

**Single fix:** **C4-03** — encrypt the outbox payload with a
worker-bound key, validate the `owner_id` server-side via a
per-event HMAC.

---

## Elite-tier test plan (per the objective)

The objective requires testing against the most sophisticated attacks
an elite hacker group would run. The chained attacks above are the
threat model. A test plan to verify the codebase resists them:

1. **Cross-PHC referral fabrication** (Chain D):
   - Setup: PHC A doctor account, PHC B case UUID (synthetic).
   - Action: POST `/api/cases/<PHC B case UUID>/refer` as PHC A doctor.
   - Assert: 403 (current code may allow — needs verification).

2. **Outbox impersonation on shared device** (Chain F):
   - Setup: Worker A account, Worker B account on same browser
     session. Both have queued outbox rows.
   - Action: Worker B reads Worker A's outbox via DevTools, modifies
     `owner_id`, syncs.
   - Assert: the server records A's user id, not B's. (Needs
     server-side owner binding.)

3. **RLS bypass via direct REST** (Chain A step 2-3):
   - Setup: low-privilege ASHA worker JWT.
   - Action: POST `/rest/v1/case_records` with
     `submitted_by = <victim UUID>`.
   - Assert: 403 (currently succeeds; **C3-01** is the gap).

4. **Pickle RCE in the .pkl** (Chain B step 5):
   - Setup: a controlled .pkl with `__reduce__` that creates a
     file in `/tmp/pwned`.
   - Action: replace `triage_classifier.pkl`, start the app.
   - Assert: the app refuses to start, or starts without
     loading the pickle. (Currently loads — **C7-01**.)

5. **JWKS endpoint spoofing** (Chain E step 6):
   - Setup: misconfigure `SUPABASE_URL` to a test server that
     returns a JWKS with a known private key.
   - Action: mint a JWT signed with the known private key.
   - Assert: 401 (currently accepts — **C5-03**).

6. **CSRF defense-in-depth** (C1-01):
   - Setup: legitimate ASHA worker session.
   - Action: from a *non-allowlisted* origin, attempt a state-
     changing request with the worker's bearer token.
   - Assert: CORS preflight fails, request blocked. (The
     CORS preflight IS the gate; the CSRF token check is
     decorative.)

7. **Rate limit bypass across workers** (C9-02):
   - Setup: 4 uvicorn workers behind a load balancer.
   - Action: send 80 `submit_case` requests in 1 minute from
     one ASHA account, distributing across workers.
   - Assert: total is 80, not 20. (Per-worker store — **C9-02**.)

8. **Schema fingerprint replay** (C3-06):
   - Setup: compute the live schema fingerprint. Modify schema
     outside any tracked migration. Recompute.
   - Assert: drift detector fires, admin is alerted.

9. **Pediatric over-triage** (C6-01):
   - Setup: synthetic 3-year-old patient, HR 175, temp 38.5.
   - Action: call `assignTier` directly.
   - Assert: tier is URGENT or ROUTINE, not EMERGENCY. (Currently
     EMERGENCY — **C6-01**.)

10. **Outbox `owner_id` swap (chain F)** — covered above.

Each test should be scripted and runnable in CI. The team should
prioritise tests 3, 4, 6, 7, and 9 (the highest-impact
single-fix-per-test).

---

## Recommended remediation priority (post-verification)

Given the chained-attack analysis, the single-fix-per-chain ordering
is:

1. **VER-07** — DROP the live database's `user_metadata` RLS policies
   (5 lines of SQL, idempotent — re-run phase32 against live). Breaks
   chain G.
2. **VER-01** — facility-scope the DSR endpoints in both Python and
   Deno (~6 lines per backend). Breaks the DSR half of chain A.
3. **VER-06** — replace the untracked `authenticated_insert` with a
   facility-scope-checked policy. Breaks chain H's first step.
4. **C7-01** — sign the `.pkl` (~30 lines of Python). Breaks chain B.
5. **VER-08** — add the untrusted-input guard to the patient-summary
   system prompt AND/OR constrain the patient-summary LLM to a fixed
   template (per-tier pre-approved phrasings). Breaks chain I.
6. **C6-01** — age-band every override in `rules.ts` (one table,
   one helper, ~6 line edits per override). Breaks chain C.
7. **C3-03** — `case_id IN (SELECT id FROM case_records WHERE
   facility_id = ...)` in the referral INSERT policy. Breaks chain D.
8. **C8-02** + **C5-03** — add Renovate for apps/api, pin
   `config.supabaseUrl`. Breaks chain E.
9. **C4-03** — encrypt outbox payload with worker-bound key,
   validate `owner_id` server-side. Breaks chain F.
10. **VER-02, VER-03, VER-04, VER-05** — defense-in-depth; addressed
    in a follow-up sprint.

After the first three fixes (VER-07, VER-01, VER-06 — all small SQL
or guard changes), the live database is no longer exploitable for
privilege-escalation or cross-tenant PHI access.

---

## Verification pass (2026-08-29 second pass)

After the original 10-cycle audit, the findings were independently
re-validated against the current code. The verifier marked one finding
as a false positive and uncovered 8 additional issues:

### False positive

- **`VN-2026-08-C2-05`** — claimed LLM prompt injection via the
  `language` query parameter on `case_patient_summary`. The code
  maps `language` through `PATIENT_SUMMARY_LANGUAGE_NAMES.get(language, "English")`
  in `llm.py:383`, so any unrecognised string resolves to `"English"`.
  No prompt injection. **Status: closed as false positive.**

### Newly verified findings (from the verification pass)

| ID | Severity | Component | One-line |
|----|----------|-----------|----------|
| [VER-01](findings/VN-2026-08-VER-01.md) | CRITICAL | DSR endpoints | PHC admin can export and erase any case across facilities (no facility check) |
| [VER-02](findings/VN-2026-08-VER-02.md) | HIGH | Staff mgmt | Global `auth.users` page != local profiles page → missing staff |
| [VER-03](findings/VN-2026-08-VER-03.md) | HIGH | push_routes | PHC admin can spam global EMERGENCY push broadcasts |
| [VER-04](findings/VN-2026-08-VER-04.md) | MEDIUM | Rate limit | Asymmetric Supabase projects + reverse proxy = shared rate-limit bucket |
| [VER-05](findings/VN-2026-08-VER-05.md) | MEDIUM | Auth | Transient profile resolution fail-open |
| [VER-06](findings/VN-2026-08-VER-06.md) | CRITICAL | Live DB | `authenticated_insert` policy on live DB has no facility or is_active check |
| [VER-07](findings/VN-2026-08-VER-07.md) | CRITICAL | Live DB | Live DB still has the `user_metadata` RLS policies phase32 was supposed to drop |
| [VER-08](findings/VN-2026-08-VER-08.md) | HIGH | LLM | Stored LLM briefing re-used as trusted input in patient-summary prompt |

### New chained attacks unlocked by the verification pass

**Chain G — `user_metadata` privilege escalation (re-introduced)** —
uses VER-07 + the standard Supabase `PUT /auth/v1/user` client-settable
metadata:

1. Any authenticated user calls `PUT /auth/v1/user` with
   `{"data": {"role": "admin"}}` (Supabase allows this on the
   service-tier auth flow).
2. Their JWT now carries `user_metadata.role = 'admin'` on the next
   refresh.
3. The live database's `asha_select_own` policy (line 365 of
   `schema_snapshot.sql`) checks `user_metadata.role` — passes the
   "doctor/admin" branch.
4. The attacker can now SELECT every case row across every facility.
5. The `doctor_update` policy (line 364) lets the attacker UPDATE
   any case row, including `triage_level` and `overridden_triage`.
6. The `profile_select` policy (line 397) lets the attacker SELECT
   every profile — including the service-role key custodian's profile.
7. The `case_referrals` policies (lines 375-377) let the attacker
   insert/update/select referrals with arbitrary `from_facility` /
   `to_facility`.

**This chain is enabled by a single untracked RLS policy on the
live database that the tracked migrations said was dropped. The
drift detector (phase28's `fn_schema_fingerprint`) is supposed to
catch this; either it is not running against the live database,
or its alerts are being ignored. The CI workflow
`db-schema-drift.yml` needs investigation.**

**Chain H — Cross-tenant case fabrication (VER-06 + VER-07)** — the
live database has both an untracked permissive INSERT policy AND
untracked permissive `user_metadata` policies. Combined:

1. Attacker (PHC A ASHA worker) PUTs `user_metadata.role = 'admin'`
   to themselves.
2. Attacker then calls `POST /rest/v1/case_records` with
   `submitted_by = own_uid, facility_id = PHC_B_UUID, triage_level = 'EMERGENCY'`.
3. `asha_select_own` (now trusts `user_metadata.role = 'admin'`) lets
   the row be visible everywhere.
4. The doctor at PHC B sees a real-looking emergency, fires the
   push notification chain.
5. The attacker, still at PHC A, observes the push fire (if they
   have any push subscription at PHC B — they don't, but the *audit
   trail* shows the push was sent).

**Chain I — Stored LLM prompt injection (VER-08)** — uses the
briefing's permissive fields (`primary_risk_driver`,
`recommended_immediate_actions`) to plant instructions that fire on
the next patient-summary call:

1. Attacker submits a case with embedded prompt-injection in a
   free-text field (e.g., `chief_complaint`). The briefing LLM is
   hardened against this for `triage_level` but its other fields
   carry the injection through.
2. The briefing is stored in `case_records.briefing`.
3. The ASHA worker later calls `/api/cases/{case_id}/patient-summary`.
4. The patient-summary LLM receives the stored briefing fields as
   trusted user-content, with no injection guard.
5. The patient-summary output is read aloud to the patient, in the
   patient's own language. The patient hears a customized message
   crafted by the attacker.

---

## Methodology and what was NOT covered

- **No live testing** — this was a static, read-only review of
  source code, migrations, and config. No HTTP requests were made
  against a live backend. The chained-attack scenarios are reasoned
  from code paths, not from observed runtime behaviour.
- **No fuzzing** — the `tools/training/smoke_test.py` and the
  clinical-core fuzz suite were not run as part of this audit.
- **No dependency CVE scan** — only the pinned versions were noted.
  An SCA tool (Snyk, Trivy, Dependabot's security tab) should be run
  on a regular cadence.
- **Limited coverage of `apps/api`'s edge cases** — only the auth,
  CSRF, idempotency, and JWKS paths were deeply reviewed. The route
  handlers (cases.ts, protocol.ts, etc.) were not read in full.
- **Limited coverage of the training pipeline** — `train_classifier.py`
  was skimmed, not deeply audited. The data generation logic
  (synthetic patient generation) is not in scope for an adversarial
  audit.
- **No review of the Vercel deploy** — `vercel.json` was read but
  the Vercel dashboard configuration is not auditable from this
  workspace.
- **No review of the Supabase dashboard configuration** — RLS
  policies, auth settings, edge function secrets, etc. are not in
  this repository.

The findings here are not exhaustive; they are the issues that
surfaced from the 10-cycle walk. A real elite red-team exercise would
include live testing, dependency scanning, and a longer engagement
(typically 2-4 weeks for a codebase of this size).
