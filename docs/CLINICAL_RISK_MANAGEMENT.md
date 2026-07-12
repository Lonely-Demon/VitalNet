# VitalNet — Clinical Risk Management File (ISO 14971-aligned)

> **Status: working draft, synthetic-data stage.** This is a structured
> hazard analysis for VitalNet's ML triage layer, written in the shape ISO
> 14971 (application of risk management to medical devices) expects. It is
> **not** a certified risk management file: several residual-risk cells are
> honestly marked *UNQUANTIFIED* because they cannot be quantified without
> real-world outcome data (see `backend/app/ml/MODEL_CARD.md`,
> `docs/CLINICAL_GOVERNANCE.md`). Its purpose is to make VitalNet's safety
> case legible and auditable — the artifact a clinical reviewer or a CDSCO
> classification exercise would start from — and to be *ready to be filled in*
> the moment real data exists.
>
> **Updated for the Round 6 rebuild** (`docs/DECISIONS.md` §33): VitalNet's
> triage logic moved to a TypeScript monorepo (`packages/clinical-core`),
> with a `rules_first` architecture that makes the deterministic rules
> engine authoritative and the trained model advisory-only. This is not yet
> in production — every entry in `apps/web/src/api/base.js`'s
> `ENDPOINT_BACKEND` map is `'legacy'`, and the cutover is explicitly gated
> on `docs/CLINICAL_REVIEW.md`'s clinician sign-off. `backend/app/ml/` (the
> live, model-primary FastAPI path) is what patients actually experience
> today, and this file's hazard analysis is written against **that** as the
> current state, with `rules_first`'s effect noted wherever it changes the
> picture once it ships.

Read alongside: `MODEL_CARD.md` (what the model is), `CLINICAL_GOVERNANCE.md`
(regulatory posture), `docs/SECURITY.md` (technical security),
`docs/VALIDATION_PROTOCOL.md` (how the open residual risks get closed),
`docs/DECISIONS.md` §33 (the Round 6 migration's full rationale and
evidence), and `docs/CLINICAL_REVIEW.md` (the sign-off gate for any change
to `packages/clinical-core/src/rules/**`).

## 1. Scope & intended use (restated for risk context)

- **Intended use:** decision *support* — triage into ROUTINE / URGENT /
  EMERGENCY to help an ASHA worker and PHC doctor prioritise. Not a diagnosis,
  not autonomous, always human-reviewed.
- **Intended users:** trained ASHA community health workers (intake) and PHC
  doctors (review).
- **Intended population/environment:** rural Indian primary care.
- **Cardinal harm this file is organised around:** **under-triage** — a
  patient who genuinely needs urgent/emergency care is classified lower and
  therefore de-prioritised or sent home. Every hazard below is scored by how
  it could contribute to that.

## 2. Risk acceptability framework

Because there is no real-world outcome data, likelihood is **qualitative**.
This is stated, not hidden — a quantified likelihood would be a fabricated
number.

**Severity (of the resulting harm):**

| Level | Meaning |
|---|---|
| S4 Catastrophic | Death or permanent disability from a missed emergency |
| S3 Serious | Serious deterioration, avoidable admission, delayed critical care |
| S2 Minor | Unnecessary escalation/visit, delay within a safe window |
| S1 Negligible | Operational annoyance, no clinical consequence |

**Likelihood:** *Frequent / Probable / Occasional / Remote / Improbable*, or
**UNQUANTIFIED** where only real data could establish it. Pre-mitigation
likelihood is a clinical-judgement estimate; post-mitigation residual is what
matters.

**Risk acceptability:** any hazard with residual **S4** and a residual
likelihood above *Improbable* is **not acceptable for real-patient
deployment** and blocks the "real deployment" milestone until closed with real
evidence. This is why VitalNet is currently positioned as pre-deployment.

## 3. Empirical basis

Two independent, complementary pieces of evidence now exist — read both, not
either in isolation.

### 3a. clinical-core's own conformance suite (primary evidence, CI-enforced)

`packages/clinical-core/test/conformance/hybrid.conformance.test.ts`
(`report.md`) compares 10,000 synthetic patients labelled by Python's live
`predict_triage()` against clinical-core's TypeScript `triage()`:

- **`hybrid` mode** (reproduces the deployed server's current semantics —
  safety net → model-authoritative → NEWS2 floor): **100.000% agreement, 0
  mismatches**. The TS port did not introduce any drift from the live system.
- **`rules_first` mode** (the target end-state — rules engine authoritative,
  model advisory-only) against that same set: **88/10,000 (0.88%) tier
  changes**, 35 upgraded, **53 downgraded**, including **51 EMERGENCY→URGENT**.
  This is the number `docs/CLINICAL_REVIEW.md` gates production cutover on —
  a named clinician must review this specific delta and the rules tables it
  comes from before `rules_first` reaches any user.

### 3b. Model-vs-rule disagreement ablation (secondary, complementary evidence)

`tools/training/ablation_model_vs_rule.py` answers a narrower, different
question than 3a: not "does today's deployed behaviour match the target
end-state," but **"how much is the deterministic guardrail layer actually
doing"** — isolating the trained model with *zero* guardrails, so the model's
own unmitigated behaviour can be seen directly. Run on 60,000 fresh
out-of-sample synthetic patients:

| Comparison | Agreement | Over-triage (safe) | **Under-triage (unsafe)** |
|---|---|---|---|
| Raw model (`clf.predict`, no guardrails) | 92.05% | 0.47% | **7.47% (4,485)** |
| Production (`predict_triage()` — safety net + NEWS2 floor + model, what's actually deployed) | 99.21% | 0.47% | **0.32% (191)** |

Of the 4,485 raw-model under-triages, **4,294 (95.7%) are rescued** by the
deterministic safety net + NEWS2 floor before they'd ever reach a user; 191
survive into production, including **130 of 16,264 rule-EMERGENCY cases
(0.80%)** shipping below EMERGENCY.

**A caveat found and verified while adapting this script for the Round 6
migration, not assumed:** the raw-model under-triage rate above (7.47%) is
*not* directly comparable to a pre-migration run of the same ablation (which
reported ~0.73%). This is a reference-standard change, not a model
regression — see §3c. The **production-path** numbers (191/130) *are*
directly comparable, and are materially unchanged from before the migration,
because `predict_triage()`'s own inference-time NEWS2 floor has not changed.

### 3c. New finding: training-label generation now includes the NEWS2 floor

Verified directly (side-by-side old-Python-vs-new-TS run on identical
generated patients, not inferred): pre-migration, `train_classifier.py`'s
label generator (`assign_triage_label`) and the inference-time NEWS2 floor
(`classifier.py::_news2_concerning_vital`, Layer 3 of `predict_triage()`)
were **two separate functions with two separate roles** — the floor ran only
at inference, never during training-label generation. clinical-core's
`assignTier()` (`packages/clinical-core/src/rules/engine.ts`) unifies both
roles behind one function — the entire point of Round 6 — which means
`packages/clinical-core/cli.mjs label` (what `train_classifier.py` now calls
to generate training labels) **applies that floor to labels too**, a scope
the old two-function split never had.

This is not dangerous — it moves training labels in the *safe* direction
(more URGENT, fewer ROUTINE near that boundary) — but it is a genuine,
previously-undocumented behavioural change with a concrete consequence: **the
next model retrain will learn from a measurably more conservative label
distribution near the ROUTINE/URGENT boundary than the currently-shipped
v3.1.0 model was trained on.** This belongs in `docs/DECISIONS.md` before
that retrain happens, not as a silent drift discovered after the fact. Flagged
here as hazard **H12** below.

**Interpretation, unchanged from the pre-migration analysis:** the
deterministic guardrails do real, load-bearing work (rescuing 95.7% of the
raw model's under-triages), but 191 cases — including 8 two-tier
EMERGENCY→ROUTINE drops in the earlier 60k-sample run — still ship triaged
*below* what the transparent evidence-based rule would assign, with no
validated justification. That is the argument for `rules_first` +
`needs_review` folding (§H1 below), now implemented and pending clinician
sign-off.

## 4. Hazard analysis table

Mitigations are cited to source so the safety case is traceable. Residual
risk assumes the mitigations are in place and working.

| # | Hazard | Cause(s) | Harm (Sev) | Pre-mit. likelihood | Mitigations (traced) | Residual |
|---|---|---|---|---|---|---|
| H1 | **Under-triage of a true emergency** (EMERGENCY→URGENT/ROUTINE) | Model error; the *rule itself* is wrong for a real presentation; out-of-distribution case | S4 | Occasional | Deterministic safety net + NEWS2 floor (`backend/app/ml/classifier.py`, still live); EMERGENCY-weighted class weights; mandatory doctor review; `low_confidence` abstention. **New, implemented, not yet live:** `rules_first` mode makes the rules engine unconditionally authoritative and folds any model/rules disagreement into `needs_review` (`apps/api/.../_shared/cases.ts::computeNeedsReview`, tested) — this eliminates under-triage-below-rule by construction once shipped | **S4 / UNQUANTIFIED** today (guardrails catch the unambiguous subset only); **improves to a stronger, tested mitigation once `rules_first` ships** — still gated on real-world validation and clinician sign-off, so still blocks unsupervised deployment |
| H2 | **Synthetic-data validity gap** — real performance ≠ synthetic metrics | Model and rules engine both learned/encode a self-authored heuristic; no real patients seen either way | S4 | Probable (that real ≠ synthetic) | Honest model card; metrics never claimed as real-world; outcome-feedback loop scaffolding | **S4 / UNQUANTIFIED** — the dominant open risk, **unaffected by the language/architecture migration**; only real data closes it |
| H3 | **Automation bias** — reviewer rubber-stamps a confident ROUTINE + fluent LLM briefing | Persuasive SHAP/rules-citation prose + LLM briefing; time pressure; over-trust | S4 | Occasional | Fixed non-removable disclaimer; `needs_review` surfacing; triage tier shown with provenance (now with citable rule IDs, e.g. `aggregate_score_7plus`, once `rules_first` ships — arguably easier to trust uncritically than SHAP prose, which cuts both ways) | **S3–S4 / UNQUANTIFIED** — human-factors validation not yet done |
| H4 | **Fragile free-text features** — negation-blind keyword matching | `clinical_features.py::_map_complaint_to_risk` / comorbidity substring matching. **Confirmed carried over unchanged** into `packages/clinical-core/src/features.ts` (`.includes(term)`, no negation handling) — the migration was a faithful port, not a rewrite, so this pre-existing issue moved codebases without being fixed | S3 | Probable | Model/rules are primarily vitals/structured-symptom driven; free-text is a minor feature | **S2–S3 / Occasional** — still open, still fixable, now in TS instead of Python |
| H5 | **Inequity / bias** — geography baked into individual triage | `_geographic_disease_risk` / `_healthcare_access_score` apply a risk multiplier from a location *string*. **Confirmed carried over unchanged** into `features.ts` (`ruralTerms`/`geographicRisk`/`healthcareAccessibility`, same logic) | S3 | Occasional | Small feature weight; documented | **S2–S3 / UNQUANTIFIED** — still open, still carried forward verbatim by the port |
| H6 | **Missing vitals under-scored** — unmeasured danger invisible | No BP cuff / pulse-ox in the field; scorer treats a missing vital as 0 (verified identical in `bands.ts::bandScore`: `if (value === null) return 0`) | S4 | Probable (rural reality) | Trained/labelled on missing-vital patterns; LLM briefing flags what was not recorded; doctor sees blanks | **S3 / Occasional** — inherent to the data-collection reality, unaffected by the migration |
| H7 | **Online/offline triage divergence** | Two runtimes (Python pkl vs JS) drift | S4 | Remote (was) | **Superseded, not just mitigated:** the Round 6 migration deleted the JS mirror entirely (`clinicalRules.js`, `treeEvaluator.js`, `validation.js`, `patientKey.js`, and the four parity-test suites that existed only to catch drift between them) — `apps/web`'s offline triage now calls `@vitalnet/clinical-core`'s `triage()` directly, the same function the (eventual) server calls. There is structurally one implementation, not two kept in sync by tests | **S1 / Improbable** — this hazard class is now closed by construction, not merely well-tested. (One live nuance: today, pre-cutover, offline runs `hybrid` mode to match the still-`legacy` server exactly — see `apps/web/src/utils/triageClassifier.js`'s header — a deliberate, documented choice, not a residual mirror.) |
| H8 | **Model/data drift over time** on real inputs | Population/seasonality shift after deployment | S3 | Probable post-deployment | `tools/training/drift_monitor.py` scaffolding (moved from `backend/scripts/`, unaffected by the rewire otherwise) | **S3 / UNQUANTIFIED** — monitor exists but has no real ground truth to alarm on |
| H9 | **LLM briefing hallucination** misleads clinician | LLM invents a differential/action | S3 | Occasional | Triage tier hard-locked post-generation (verified unchanged in both the live `backend/app/services/llm.py` and the ported `apps/api/.../_shared/llm.ts`: `briefing.triage_level = triageResult.triage_level // SAFETY: LLM cannot override`); prompt-injection sanitisation; fixed disclaimer; fallback briefing | **S2–S3 / Occasional** — tier is protected on both current and future backends; briefing *prose* remains unvalidated |
| H10 | **Triage record tampering** post-submission | `case_records` UPDATE RLS does not restrict columns (red-team audit finding) | S3 | Occasional | App-layer authz + audit log (bypassable via direct PostgREST) | **S3 / Occasional** — unaffected by this migration; fix still pending, tracked separately |
| H11 | **Model fails to load** → no triage | Corrupt pkl / sklearn version mismatch (legacy path); tree-JSON/model artifact missing offline (clinical-core path) | S2 | Remote | Fail-safe: legacy rules-based fallback boot; offline `runTriage()` falls back to an override-only safety check (never a guessed tier) when the model can't load, reporting `triageLevel: null` ("pending") rather than fabricating a result — verified in `triageClassifier.js` | **S1–S2 / Improbable** — fail-safe direction preserved and, on the offline path, made more conservative (no-guess over guess) |
| H12 | **New — training-label distribution shift** (Round 6) | `assignTier()` unifies label-generation and inference-time roles, so the NEWS2 floor (previously inference-only) now also shapes training labels — see §3c | S2 | Occasional (next retrain only; does not affect the currently-shipped v3.1.0 model, which was trained pre-migration) | Documented here (§3c); the shift moves labels in the *safe* direction (more conservative) | **S1–S2 / Occasional** — low severity (safe-direction label shift), but **needs a `DECISIONS.md` entry and a before/after label-distribution comparison at the NEXT retrain**, not silent adoption |

## 5. Risk-benefit & the deployment gate

At the current stage the **benefit** (prioritisation support for an
over-stretched ASHA/PHC workflow, with deterministic emergency guardrails) is
real, but the **residual S4 hazards H1–H3 and H6 are UNQUANTIFIED**. Under the
acceptability rule in §2, that means: **acceptable as a supervised
decision-support prototype with a human reviewing every case; NOT acceptable
as an autonomous or unsupervised real-patient device.** The gate to change
that verdict is real-world evidence, per `docs/VALIDATION_PROTOCOL.md` — and,
separately, `docs/CLINICAL_REVIEW.md`'s clinician sign-off before `rules_first`
(and therefore H1's improved mitigation) reaches any user.

## 6. Traceability & maintenance

- Each hazard should trace forward to a test and/or a monitoring signal.
- Re-review this file on any change to `packages/clinical-core/src/rules/**`,
  `packages/clinical-core/src/features.ts`, `backend/app/ml/classifier.py`
  (while it remains live), or the intended-use statement.
- This file is versioned with the model; record the `model_version` it was
  last reviewed against below.
- H1's status is tied to `docs/CLINICAL_REVIEW.md`'s sign-off — re-check that
  gate's state before treating H1 as "improved" rather than "unquantified."

_Last reviewed against model_version: 3.1.0 (unchanged/unretrained by the
Round 6 migration — see H12). Reviewed against `docs/DECISIONS.md` §33 and
the Round 6 rebuild (TypeScript migration, `rules_first` architecture,
unified outbox) — not yet in production._
