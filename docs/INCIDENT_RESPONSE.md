# VitalNet — Security Incident Response Plan

This is the runbook for a **security incident**: unauthorized access,
credential compromise, a PHI exposure, an exploited vulnerability, or
anything else where someone got data or access they shouldn't have. For
data-loss/infrastructure failures with no adversary involved (a bad
migration, a deleted table, a failed deploy), see
`docs/DISASTER_RECOVERY.md` instead — the two overlap (a breach can also
require a restore) but are triggered by different things and have
different first moves. For how to *report* a vulnerability you found
(rather than respond to one already happening), see `docs/SECURITY.md`'s
"Reporting a vulnerability" section.

## Scope and severity

| Severity | Examples | Response time target |
|---|---|---|
| **Critical (SEV1)** | Confirmed PHI exposure/exfiltration; `SUPABASE_SERVICE_ROLE_KEY` or `GROQ_API_KEY` leaked publicly; an active exploit against production | Immediate — page whoever's on call, don't wait for a meeting |
| **High (SEV2)** | A vulnerability that *could* expose PHI or bypass auth, not yet confirmed exploited; a dependency CVE with a known public exploit | Same business day |
| **Medium (SEV3)** | A vulnerability requiring unusual preconditions to exploit; a Dependabot alert with no known active exploit | Within the current sprint |
| **Low (SEV4)** | Hardening opportunities, defense-in-depth gaps with no direct exploit path | Normal backlog |

When in doubt, classify one level higher until triage says otherwise —
under-reacting to a real PHI exposure is a much worse failure mode than a
false alarm.

## Roles (fill in for your deployment)

| Role | Responsibility | Contact |
|---|---|---|
| Incident Commander | Owns the response, makes the call/contain/communicate decisions | [Name/contact] |
| Security Lead | Technical investigation, containment, root cause | [Name/contact] |
| Clinical Operations Lead | Assesses patient-safety impact, decides if facilities need direct notice | [Name/contact] |
| Data Protection contact | DPDP Act obligations — Data Protection Board / data-principal notification (`docs/COMPLIANCE_DPDP.md`) | [Name/contact] |

(Mirrors `docs/DISASTER_RECOVERY.md` §7's contact table — keep both in sync
if your org uses the same people for both.)

## The five phases

### 1. Detection

Signals that should trigger this runbook:
- An unexpected pattern in `phi_audit_log` (`docs/SECURITY.md`'s audit
  trail) — a burst of `PHI_READ`/`PHI_EXPORT` events from one account, an
  admin action nobody on the team recognizes, access from an unfamiliar
  facility_id.
- A GitHub secret-scanning or Dependabot alert on a real (not test/synthetic)
  credential.
- A CodeQL/security-audit finding that turns out to be actively exploitable,
  not just theoretical.
- A user or facility reporting something anomalous (login they didn't
  perform, data they didn't submit appearing under their account).
- Rate-limiting or auth-failure spikes suggesting credential stuffing or
  brute-force against `/api/auth/*` or the JWT-bearing endpoints.

### 2. Triage

- Classify severity (table above).
- Identify scope: which accounts, which facility/facilities, which case
  records (`case_id`s), what time window. `phi_audit_log` is the primary
  forensic source — every PHI create/read/update/delete/export is in
  there with user, role, resource, facility, IP, and timestamp
  (`app/core/audit.py`).
- Identify whether the incident is still active (ongoing unauthorized
  access) or historical (already stopped, you're investigating after the
  fact) — this changes whether containment is urgent-immediate or can be
  sequenced after evidence collection.

### 3. Containment

Depending on what's compromised:
- **Leaked/compromised credential** (Supabase service-role key, Groq/Gemini
  key, VAPID keys, JWT secret): rotate it immediately in Supabase/the
  provider dashboard, update the deployment's environment variables
  (Railway/Vercel), redeploy. A leaked `SUPABASE_JWT_SECRET` additionally
  invalidates every currently-issued token — expect every user to be
  logged out and need to re-authenticate.
- **Compromised user account**: use `PATCH /api/admin/users/{id}` /
  `is_active: false` (or the dedicated deactivate flow) to disable it
  immediately; audit-log review shows what that account touched during the
  compromise window.
- **Actively exploited vulnerability in the app itself**: the fastest safe
  containment is usually disabling the specific affected route/feature
  (feature-flag it off or redeploy a hotfix) rather than taking the whole
  API down — check whether the vulnerability is isolated to one router
  module first.
- **Suspected RLS/authorization bypass**: `docs/DECISIONS.md` §7 is the
  reference for which surfaces are RLS-backstopped vs. `require_role()`-only
  (the entire `/api/admin/*` and `/api/admin/cases/*` DSR surface, per
  `test_admin_authz.py`, is `require_role('admin')`-only with **no** RLS
  backstop — if that boundary is ever the vector, containment must assume
  every table `supabase_admin` can touch was in scope).

### 4. Eradication and recovery

- Confirm the vulnerability/vector is actually fixed (not just contained) —
  a patch merged and deployed, not just a workaround.
- Rotate any credential that was anywhere near the incident, even ones
  not confirmed leaked, if rotation cost is low.
- Restore any data integrity issue via `docs/DISASTER_RECOVERY.md`'s
  restore procedures if the incident altered/deleted records.
- Re-enable anything disabled in containment once the fix is verified.

### 5. Post-incident review

- Write up: timeline, root cause, what data/accounts were actually
  affected (not just potentially affected), what fixed it, what would have
  caught it sooner.
- File the fix as a normal PR through `CONTRIBUTING.md`'s process — an
  incident fix is still real code that needs review and CI, urgency isn't
  a reason to skip either.
- Add a regression test where practical (mirrors this repo's existing
  pattern: `test_admin_authz.py` and the round-1 IDOR fix both trace back
  to a specific incident/finding gaining a permanent regression test).
- Update this document or `docs/SECURITY.md` if the incident revealed a
  gap in either.

## PHI breach — DPDP Act notification duty

If the incident involved actual (not just potential) unauthorized access
to patient data, `docs/COMPLIANCE_DPDP.md`'s breach-notification section
applies: the Data Fiduciary (whoever operates this deployment) has a
notification duty to the Data Protection Board and affected data
principals under the DPDP Act. This document's forensic phase (2) is what
scopes *who was affected*, which is a prerequisite for that notification —
but the notification decision and process itself is a legal/organisational
one this codebase cannot automate, same caveat as `docs/COMPLIANCE_DPDP.md`
states throughout. Loop in the Data Protection contact (roles table above)
as soon as PHI exposure is confirmed, not after eradication — notification
timing may not wait for a full post-incident review.

## What this plan is not

This is a runbook for the *response*, not a compliance certification and
not a substitute for a real security program. It doesn't include things
that only make sense for an org with actual production traffic and an
actual security team on call (a paging system, an external forensics
retainer, a cyber-insurance claims process) — add those sections when this
deployment reaches the scale that needs them, rather than filling them in
speculatively now.
