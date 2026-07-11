# VitalNet — Clinical Review Gate

This is the sign-off process for any change to VitalNet's deterministic
clinical rules (`packages/clinical-core/src/rules/**` and `bands.ts`) — the
code that decides ROUTINE/URGENT/EMERGENCY. `CODEOWNERS` requires a review
on that path for every PR; this document is what that review is actually
checking, and the specific outstanding item that gates the Round 6
rules-first cutover (`docs/DECISIONS.md` §33). Companion documents:
`docs/CLINICAL_GOVERNANCE.md` (regulatory posture, guardrail architecture,
model lifecycle) and `backend/app/ml/MODEL_CARD.md` (model specifics).

**Honesty note, matching `CLINICAL_GOVERNANCE.md`'s convention**: nothing in
this document claims a completed clinical review has happened. As of this
writing, no named clinician has signed off on the rules-first cutover — see
"Outstanding: the rules-first cutover" below. This document exists so that
gap is explicit and blocking, not quietly assumed away.

## The checklist (required for any PR touching `rules/**` or `bands.ts`)

A reviewer with `CODEOWNERS` authority on this path confirms all three
before approving:

### 1. Citation verified

Every band, threshold, and override in `bands.ts`/`rules.ts` carries an
inline citation (NEWS2, qSOFA/Sepsis-3, APLS/PALS paediatric reference
ranges, ACOG for the preeclampsia rule, or an explicit "deliberate
departure from X because Y" comment where VitalNet's population differs
from the cited framework's assumptions — e.g. the widened hypertensive-BP
band, or age-banded paediatric thresholds replacing adult NEWS2 bands). A
changed or new threshold without a traceable citation (or an explicit,
reasoned departure) does not pass review, regardless of how well it scores
on synthetic data — a rule that fits the training distribution well but
has no clinical grounding is exactly the failure mode this gate exists to
catch.

### 2. Test vectors reviewed

- Every rule change ships with new or updated `{input, expect}` vectors
  embedded next to the rule it tests (`packages/clinical-core/test/
  engine.test.ts`, `contraindications.test.ts`) — not just a passing
  existing suite. The reviewer reads the new vectors, not just their
  count.
- `engine.fuzz.test.ts` (6,000+ randomized schema-reachable cases: never
  crashes, output contract always holds) still passes.
- If the change could plausibly shift the tier on real cases at the
  population level (not just the specific vector added), regenerate the
  conformance report (`tools/training/export_conformance_patients.py` +
  `pnpm --filter @vitalnet/clinical-core test`) and read the new delta in
  `packages/clinical-core/test/conformance/report.md` — specifically the
  confusion matrix's off-diagonal cells. A change that moves patients from
  EMERGENCY to a lower tier gets read line-by-line, not just totalled.

### 3. Clinician approver named

The PR description names a specific clinician reviewer (not "reviewed by
the team") who confirms sign-off #1 and #2 above are clinically sound, not
just internally consistent. Until VitalNet has a standing clinical advisor
relationship, this is satisfied by an explicit, named, dated approval
recorded in the PR itself — a software reviewer's sign-off on code
correctness is necessary but never sufficient for a change to `rules/**`.

## Outstanding: the rules-first cutover

This is the specific, current, blocking item — read in full before
enabling `rules_first` mode for any production traffic (i.e. before
flipping any entry in `apps/web/src/api/base.js`'s `ENDPOINT_BACKEND` map
from `'legacy'` to `'edge'`, or standing up `apps/api` as a production
destination by any other route).

**What changed**: `docs/DECISIONS.md` §33 made the deterministic rules
engine authoritative over `triage_level`, replacing the current live
design where the trained model is primary (wrapped by a safety net and
NEWS2 floor). Verified: **100.000% agreement** between clinical-core in
`hybrid` mode (reproducing today's exact production logic) and the live
Python backend, on 10,000 synthetic patients — proof the TypeScript port
changed nothing. Separately measured: replaying the same 10,000 patients
in `rules_first` mode instead changes the tier on **88/10,000 (0.88%)** —
35 upgraded, 53 downgraded. Full confusion matrix:
`packages/clinical-core/test/conformance/report.md`.

**The specific number that needs a clinician's eyes**: **51 of the 10,000
patients move from EMERGENCY (today's live model output) to URGENT
(rules_first)**. This is not evidence of a bug — the model was trained on
the rules engine's own labels and is expected to drift from them on
borderline cases, and the direction (rules engine correcting a model
over-call) is not obviously the wrong one. But "not obviously wrong" is a
software engineer's judgment, not a clinical one, and a change that moves
51-in-10,000 patients out of the EMERGENCY bucket is exactly the class of
change this whole document exists to gate.

**What sign-off requires, concretely**:
1. A named clinician reviews a representative sample of the 51
   downgrades — not just the aggregate count — using
   `packages/clinical-core/test/conformance/report.md`'s "sample of changed
   cases" (currently the first 20 of the full 88; expand the sample if
   needed) cross-referenced against the actual patient vectors in
   `packages/clinical-core/test/conformance/patients_with_python_tier.jsonl`.
2. The clinician either (a) confirms the downgrades are clinically
   reasonable (the model was over-calling EMERGENCY on cases a human
   reviewer would triage URGENT) and signs off, or (b) identifies a
   pattern worth fixing in the rules engine first, in which case this
   becomes a `rules/**` PR that itself goes through the checklist above.
3. The sign-off (name, date, decision, and any caveats) is recorded as an
   addendum to this section, in a follow-up PR — not implied by this
   document's existence.

**Until that sign-off is recorded here, `rules_first` does not go live.**
This is independent of `apps/api`'s own readiness (test coverage,
JWKS/ES256 auth, webpush — see `apps/api/README.md`'s status section):
software readiness and clinical sign-off are two separate gates, and both
must clear before cutover.

### Sign-off record

_(Empty. No clinician sign-off has occurred yet — see above.)_
