# VitalNet — Validation Readiness & Protocol

> **Status: public-data evaluation cycle completed; clinical validation not achieved.** VitalNet has now been evaluated on authorized real public datasets under strict local-only controls. This document records what those evaluations establish and what remains hard-gated on a qualified clinical collaborator, prospective site, ethics approval, and appropriate reference standards. The consolidated findings are in `docs/evaluation/PUBLIC_DATA_EVALUATION_CLOSURE.md`.
>
> **Updated for the Round 6 rebuild** (`docs/DECISIONS.md` §33): the triage
> logic moved to `packages/clinical-core` (TypeScript), with a `rules_first`
> architecture and `docs/CLINICAL_REVIEW.md` as the clinician-sign-off gate.
> None of this is in production yet — `backend/app/ml/` remains what patients
> actually experience. This plan's substance is unchanged by the language
> migration; only file paths and a couple of statuses are updated below.

Companion to `backend/app/ml/MODEL_CARD.md`, `docs/CLINICAL_GOVERNANCE.md`,
`docs/CLINICAL_RISK_MANAGEMENT.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`,
`docs/RULES_PRIMARY_DESIGN.md`, and `docs/CLINICAL_REVIEW.md`.

## 0. The two unlocks (the actual bottleneck)

| Unlock | What it enables | Status |
|---|---|---|
| **A clinical collaborator** (community/EM physician, ASHA medical officer, or an NGO like Khushi Baby) | Sign-off on the triage *logic*; adjudicated reference labels; human-factors review | **Not yet — pursue first (more attainable, unblocks more).** `docs/CLINICAL_REVIEW.md` now exists as the concrete artifact to hand them: a reviewable ruleset with a named, quantified delta (51 EMERGENCY→URGENT cases) to sign off on, not an abstract ask. |
| **Real de-identified data** (a PHC, an NGO cohort, or VitalNet's own outcome-feedback loop) | Real discrimination/calibration, subgroup fairness, external validation | **Not yet.** Language-agnostic — the TS migration does not change this. |

No engineering on synthetic data substitutes for either. The plan is therefore
weighted toward *making these unlocks easier to obtain* (Part A produces the
clinician-reviewable artifacts that lower the bar for a "yes").

## Part A — Executable now (synthetic-only, no clinician)

These advance the safety case and the deployment goal without new resources.

- **A1 — Model-vs-rule disagreement ablation.** *Done, adapted for Round 6* —
  `tools/training/ablation_model_vs_rule.py` (moved from `backend/scripts/`,
  rewired to label via `clinical-core`'s `cli.mjs` bridge instead of a
  standalone Python function — the same bridge `train_classifier.py` itself
  now uses, so this ablation measures the SAME rules engine that's actually
  authoritative). Results and a genuine new finding from the adaptation:
  `docs/CLINICAL_RISK_MANAGEMENT.md` §3.
- **A2 — ISO 14971 hazard analysis.** *Done, updated for Round 6* —
  `docs/CLINICAL_RISK_MANAGEMENT.md`.
- **A3 — First-class evaluation harness.** *Adapted for Round 6* —
  `tools/training/evaluate_on_real.py` (moved from `backend/scripts/`, path
  fix only — it evaluates the still-live `backend/app/ml/classifier.py`, which
  the migration didn't touch). Reports, given a labelled dataset (synthetic
  today, real later): sensitivity/specificity/PPV/NPV with Wilson 95% CIs,
  per-tier confusion, the EMERGENCY under-triage safety rate, calibration,
  subgroup slices, and the real-data guardrail lift. **New follow-up
  identified, not yet done:** once `rules_first` ships, this harness should
  gain a second mode evaluating `assignTier()` directly (via the same
  `cli.mjs` bridge), so real data can validate the rules engine on its own —
  not just the model wrapped in it. Tracked here, not implemented.
- **A4 — Retire the fragile/biasing features (hazards H4, H5).** *Still
  open.* Verified directly: both carried over unchanged into
  `packages/clinical-core/src/features.ts` during the port (negation-blind
  keyword matching, geography-as-individual-risk). The migration was a
  faithful port, not a fix pass — this is still on the backlog, now in a
  different file. Re-run `pnpm --filter @vitalnet/clinical-core test` after
  any change here.
- **A5 — Ground the labels in a validated instrument.** Map (and where
  appropriate, replace) `packages/clinical-core/src/rules/engine.ts`'s
  scorer against published, population-appropriate tools — **WHO ETAT** and
  **IMCI** (paediatric/rural), and the **South African Triage Score (SATS)**
  — so labels and claims trace to literature, not to us. NEWS2 alone is not
  validated for this population. (This is now a single, TS-side change
  instead of two — a direct benefit of the consolidation.)
- **A6 — Human-factors review of automation bias (hazard H3).** Structured
  walkthrough of how a confident ROUTINE + fluent LLM briefing is presented to
  the reviewer, and whether the `low_confidence`/`needs_review` signals
  (including, once shipped, model/rules disagreement) actually change
  behaviour. Write findings even without a formal usability study.
- **A7 — Rules-primary architecture inversion.** *Implemented, pending
  sign-off* — `docs/RULES_PRIMARY_DESIGN.md` proposed this; the Round 6
  rebuild (`docs/DECISIONS.md` §33) implemented it as `rules_first` mode in
  `packages/clinical-core/src/triage.ts`, in a **purer form** than the
  original design's `max(T_rule, T_model)` proposal — `rules_first` makes
  `T_final = T_rule` unconditionally (the model never influences the tier in
  either direction, only feeds `modelAgreed` → `needs_review`). **Not live**:
  every `apps/web`/`apps/api` endpoint remains `'legacy'`
  (model-primary), gated on `docs/CLINICAL_REVIEW.md`'s clinician sign-off of
  the 51-case delta.
- **A8 — External validation on real public data (completed cycle).** The authorized cycle covered Iran ED inspection, NHAMCS 2022 partial-input proxy scoring, the synthetic ASHA input-contract study, and Korean KTAS 2019 Gate 3A scoring. The consolidated report is `docs/evaluation/PUBLIC_DATA_EVALUATION_CLOSURE.md`. The results show serious emergency under-triage signals: NHAMCS emergency sensitivity 14.4%, KTAS primary emergency sensitivity 25.2%, and KTAS vital-only emergency sensitivity 17.9%. MIMIC-IV-ED remains deferred because credentialing was not completed; no full MIMIC score exists. No result constitutes clinical validation or supports deployment.

- **A9 — Safety-remediation design gate.** Before any candidate model or input-contract implementation, define the missing-context policy, required ASHA/PHC fields, insufficient-information behavior, human escalation path, pre-registered safety metrics, subgroup strata, and clinical acceptance-criteria owner. This gate is design-only until a qualified clinical/domain reviewer participates. Any candidate must first be compared with the frozen baseline on synthetic fixtures; any real-data rerun requires fresh dataset-specific authorization.

## Part B — Retrospective validation study (gated on real data)

Design it now to **TRIPOD+AI**; execute when a dataset exists.

- **Objective:** estimate real-world discrimination, calibration, and clinical
  utility of VitalNet triage against an adjudicated reference standard.
- **Design:** retrospective, on de-identified PHC records with known outcomes.
- **Reference standard (ground truth):** clinician-adjudicated triage and/or
  hard outcomes (admission, referral, deterioration, death) — **not** the
  synthetic heuristic. Define adjudication rules and inter-rater agreement up
  front.
- **Predictors:** exactly the intake fields the model uses; freeze feature
  engineering; log missingness (this population has heavy missing vitals).
- **Sample size:** power for the EMERGENCY tier (the scarce, safety-critical
  class) with acceptable CI width on sensitivity — pre-register the target.
- **Analysis:** per §A3 metrics, plus explicit **safety analysis of
  under-triage** (rate and characteristics of missed emergencies), and
  performance **with vs. without** the deterministic guardrails to quantify
  their real-world contribution. Once `rules_first` has shipped, also run
  the rules engine alone (no model) as its own arm — the whole point of the
  architecture is that it should be independently validatable.
- **Missing data:** analyse as its own stratum; do not impute silently.
- **Reporting:** full TRIPOD+AI checklist; publish limitations honestly.

## Part C — Silent / shadow deployment (gated on clinician + a site)

Before any influence on care: run VitalNet **in parallel**, its output hidden
from clinicians, and compare its triage to the clinician's real decision over a
defined period. This surfaces real-world failure modes with **zero patient
risk**. Only after acceptable shadow performance + ethics approval does the
output become visible as decision support. Prospective validation follows.
(Whichever backend is live at that point — `backend/app/` or `apps/api` — the
shadow-deployment discipline is the same.)

## Part D — Regulatory pathway checkpoints (CDSCO SaMD, India)

Per `docs/CLINICAL_GOVERNANCE.md`: confirm SaMD risk classification, assemble
the QMS/verification/validation documentation set, and treat the retraining/
outcome loop as post-market change control under the AI/ML update expectations.
Engage regulatory expertise before any clinical claim.

## Definition of done — deployment go/no-go

Real-patient decision-support deployment is **blocked** until *all* hold:

1. Residual S4 hazards (H1–H3, H6) quantified on **real** data and shown
   acceptable (`CLINICAL_RISK_MANAGEMENT.md §2`).
2. Retrospective validation (Part B) meets pre-registered sensitivity/
   calibration/subgroup thresholds, TRIPOD+AI reported.
3. Successful silent deployment (Part C) at ≥1 real site.
4. Clinical collaborator sign-off on triage logic and intended use
   (`docs/CLINICAL_REVIEW.md`).
5. Regulatory classification + documentation (Part D) complete.

Until then VitalNet is, and should be described as, a **supervised
decision-support prototype** — every case reviewed by a human, no autonomous
action.
