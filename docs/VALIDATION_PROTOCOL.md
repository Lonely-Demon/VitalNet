# VitalNet — Validation Readiness & Protocol

> **Status: pre-data plan.** VitalNet has never seen a real patient. This
> document is the plan to change that responsibly. It separates work that is
> executable **now** (synthetic-only, no clinician) from work that is
> **hard-gated** on two unlocks VitalNet does not yet have — real de-identified
> data and a clinical collaborator. Its second purpose is to make VitalNet
> *validation-ready*: so that on the day either unlock arrives, evaluation is a
> command, not a rebuild.

Companion to `backend/app/ml/MODEL_CARD.md`, `docs/CLINICAL_GOVERNANCE.md`,
`docs/CLINICAL_RISK_MANAGEMENT.md`, `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`,
and `docs/RULES_PRIMARY_DESIGN.md`.

## 0. The two unlocks (the actual bottleneck)

| Unlock | What it enables | Status |
|---|---|---|
| **A clinical collaborator** (community/EM physician, ASHA medical officer, or an NGO like Khushi Baby) | Sign-off on the triage *logic*; adjudicated reference labels; human-factors review | **Not yet — pursue first (more attainable, unblocks more)** |
| **Real de-identified data** (a PHC, an NGO cohort, or VitalNet's own outcome-feedback loop) | Real discrimination/calibration, subgroup fairness, external validation | **Not yet** |

No engineering on synthetic data substitutes for either. The plan is therefore
weighted toward *making these unlocks easier to obtain* (Part A produces the
clinician-reviewable artifacts that lower the bar for a "yes").

## Part A — Executable now (synthetic-only, no clinician)

These advance the safety case and the deployment goal without new resources.

- **A1 — Model-vs-rule disagreement ablation.** *Done* —
  `backend/scripts/ablation_model_vs_rule.py`, results in
  `docs/CLINICAL_RISK_MANAGEMENT.md §3`. Decides the rules-primary question on
  evidence.
- **A2 — ISO 14971 hazard analysis.** *Done* — `docs/CLINICAL_RISK_MANAGEMENT.md`.
- **A3 — First-class evaluation harness.** *Started* —
  `backend/scripts/evaluate_on_real.py` reports, given a labelled dataset
  (synthetic today, real later): sensitivity/specificity/PPV/NPV **with Wilson
  95% CIs**, per-tier confusion, the **EMERGENCY under-triage safety rate**,
  **calibration** (reliability + ECE), **subgroup** slices (age band, sex,
  missing-vital cohorts), and the real-data **guardrail lift**. Wire real data
  in by swapping the input only. Remaining: add decision-curve / net-benefit.
- **A4 — Retire the fragile/biasing features (hazards H4, H5).** Replace
  negation-blind free-text keyword matching; reconsider location-as-individual-
  risk multipliers. Re-run parity tests after any `clinical_features.py` change.
- **A5 — Ground the labels in a validated instrument.** Map (and where
  appropriate, replace) the bespoke `assign_triage_label` scorer against
  published, population-appropriate tools — **WHO ETAT** and **IMCI**
  (paediatric/rural), and the **South African Triage Score (SATS)** — so labels
  and claims trace to literature, not to us. NEWS2 alone is not validated for
  this population.
- **A6 — Human-factors review of automation bias (hazard H3).** Structured
  walkthrough of how a confident ROUTINE + fluent LLM briefing is presented to
  the reviewer, and whether the `low_confidence`/`needs_review` signals
  actually change behaviour. Write findings even without a formal usability
  study.
- **A7 — Rules-primary architecture inversion.** *Designed* —
  `docs/RULES_PRIMARY_DESIGN.md`. A1 confirmed the model's surviving deviations
  are net-negative on safety, so the design makes the deterministic scorer the
  *primary* triage (`T_final = max(T_rule, T_model)`) and demotes the ML to a
  safe-direction-only escalator + logged advisory disagreement. Preserves
  auditability and makes clinician sign-off tractable. **Not wired in** —
  gated on the §5 validation gate in that doc.

- **A8 — External validation on real public data (no clinician needed).**
  See `docs/DATA_ACQUISITION_AND_EXTERNAL_VALIDATION.md`: acquire a real,
  clinician-labelled ED dataset (MIMIC-IV-ED is the best fit) under its licence,
  map it to VitalNet's schema, and run it through A3's harness. This is the
  highest-probability way to attack hazard H2 without a clinician — the first
  real-patient signal VitalNet has ever had (on a proxy population; caveats in
  that doc).

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
  their real-world contribution.
- **Missing data:** analyse as its own stratum; do not impute silently.
- **Reporting:** full TRIPOD+AI checklist; publish limitations honestly.

## Part C — Silent / shadow deployment (gated on clinician + a site)

Before any influence on care: run VitalNet **in parallel**, its output hidden
from clinicians, and compare its triage to the clinician's real decision over a
defined period. This surfaces real-world failure modes with **zero patient
risk**. Only after acceptable shadow performance + ethics approval does the
output become visible as decision support. Prospective validation follows.

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
4. Clinical collaborator sign-off on triage logic and intended use.
5. Regulatory classification + documentation (Part D) complete.

Until then VitalNet is, and should be described as, a **supervised
decision-support prototype** — every case reviewed by a human, no autonomous
action.
