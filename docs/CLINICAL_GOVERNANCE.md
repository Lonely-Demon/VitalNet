# VitalNet — Clinical Governance

VitalNet is Software as a Medical Device (SaMD)-adjacent clinical decision
support: it triages a patient into ROUTINE / URGENT / EMERGENCY to help an
ASHA worker and a PHC doctor prioritise care. This document is the honest,
current governance record — what VitalNet's regulatory posture is, what
change control exists, and what would be required before any claim of
clinical validation. It complements `backend/app/ml/MODEL_CARD.md` (model
specifics) and `docs/SECURITY.md` (technical security model); read all
three together before making a regulatory or clinical-safety claim about
this system.

## Regulatory status: not cleared, by design honesty

**VitalNet has no regulatory clearance from any authority — CDSCO, FDA, CE,
or otherwise — and is not undergoing clinical trial validation.** This is
stated plainly and repeated in the model card and in-app disclaimers because
overclaiming clinical validation on a synthetic-data model would itself be a
patient-safety failure.

### CDSCO Draft Guidance on Medical Device Software (October 2025)

India's Central Drugs Standard Control Organisation (CDSCO) issued Draft
Guidance on Medical Device Software in October 2025, establishing a
risk-based classification for Software as a Medical Device (Class A, lowest
risk, through Class D, highest), based on: the software's medical purpose,
the significance of the information it provides to a healthcare decision,
and the severity of the health condition or situation it addresses. It
requires documentation across design and architecture, verification and
validation, testing, and release, with an explicit quality-management-system
and cybersecurity expectation, and calls out additional vigilance for AI/ML
software that continues to update after deployment.

**Where VitalNet plausibly sits, and why that's not a self-certification:**
VitalNet informs but does not replace a clinician's decision (a doctor
reviews every case; the ASHA worker and doctor retain full clinical
judgment), which is the profile of a lower-risk informational/triage-support
tool rather than a closed-loop diagnostic or therapeutic device. That
reasoning is offered here as a working hypothesis for a future formal
classification exercise — **it is not a CDSCO submission, a legal opinion,
or a substitute for engaging a regulatory consultant** before any real
deployment. Anyone taking VitalNet into a live clinical setting in India
must run an actual classification and gap assessment against the final
(non-draft) guidance in force at that time.

**What this document commits to, ahead of any formal submission:**
- Maintaining a versioned model card with honest performance-claim scoping
  (see `MODEL_CARD.md` — accuracy is measured against a synthetic label
  generator, not against real clinical outcomes).
- Maintaining change control over the trained model (below) so any future
  auditor can reconstruct what model version produced what output, when.
- Keeping the human-in-the-loop guarantee load-bearing in the architecture,
  not just the documentation (see "Guardrails" below).

## Intended use and human-in-the-loop guarantee

Restated from the model card because it's the single most important
governance fact: VitalNet is **decision support for a qualified health
worker**, not an autonomous diagnostic or treatment system.

- An ASHA worker collects vitals and symptoms; a triage classification is
  produced (online: server model; offline: identical-by-parity JS tree
  evaluator, see `docs/DECISIONS.md` §2).
- Every case is reviewable by a doctor. Doctors can override the triage
  classification and record the real outcome (`case_outcomes`), which is
  the mechanism by which VitalNet could, in principle, someday be validated
  against real clinical outcomes rather than a synthetic label generator.
- The LLM-generated clinical briefing (`app/services/llm.py`) carries a
  fixed, non-removable disclaimer — it is never presented as a diagnosis.

## Five-layer guardrail architecture

VitalNet's safety design separates concerns so that no single failure —
model error, LLM hallucination, or a novel presentation the model never
saw — silently produces a false sense of safety:

1. **Input validation** — Pydantic-bounded vitals/symptom schemas
   (`app/models/schemas.py`) reject physiologically impossible inputs
   before they reach the model.
2. **LLM-independent triage** — the ROUTINE/URGENT/EMERGENCY classification
   never depends on the LLM. The LLM only narrates a briefing *after* the
   deterministic/ML triage has already been decided; an LLM outage or
   hallucination cannot change a triage class.
3. **Mandatory uncertainty signalling** — the `low_confidence` abstention
   flag (`MODEL_CARD.md`) surfaces to the doctor whenever the top-class
   probability or top-two margin is weak, rather than presenting a
   falsely-confident number.
4. **Non-removable disclaimer** — every LLM briefing states this is
   decision support, not a diagnosis, and every UI surface treats the
   triage output as preliminary and reviewable, never final.
5. **Accountability separation** — the ASHA worker is responsible for data
   accuracy at collection time; the doctor is responsible for clinical
   judgment and the final care decision; VitalNet is responsible only for
   transparent, explainable, reviewable output (SHAP feature attribution,
   `MODEL_CARD.md`). No party is asked to trust the system blindly, and no
   layer is asked to compensate for another's failure silently.

This is not new to this document — it is the architecture already built
(safety net + NEWS2 floor + abstention flag + SHAP + audit log). This
section makes the design intent explicit as a governance artifact so it can
be audited, not just inferred from source.

## Model lifecycle governance

- **Versioning:** the model version (`MODEL_CARD.md` header) is bumped on
  any change to `clinical_features.py`, the training script, or the
  synthetic generator. `backend/CLASSIFIER_CHANGELOG.md` is the append-only
  history of what changed and why for every version.
- **Provenance per case:** each stored case record carries the model
  version that produced its triage (`app/ml/README.md`,
  `phase17_triage_provenance_and_override.sql`) — a doctor or auditor can
  always answer "which model made this call."
- **Change control:** the model `.pkl`, the frontend `triage_trees.json`,
  and the golden-vector test fixtures are regenerated **together, from one
  command** (`scripts/train_classifier.py`) and never edited independently
  — see `backend/README.md`. A parity test (`test_feature_parity.py` /
  `featureParity.test.mjs`) fails CI if the two runtimes ever disagree.
- **Retraining is human-gated, never automatic:**
  `scripts/retrain_from_outcomes.py` blends real doctor-recorded outcomes
  with synthetic data but does not auto-deploy; a human reviews the new
  model's metrics against the committed model card before it replaces the
  running model.
- **Fairness and drift monitoring:** `backend/scripts/fairness_audit.py` and
  `backend/scripts/drift_monitor.py` (operator-run, see `app/ml/README.md`)
  give an auditor a repeatable way to check for subgroup performance gaps
  and live-data drift against the training distribution ahead of any
  retraining decision.

## Adverse-event / incident handling hook

A "the model was wrong and it mattered" event is a clinical-safety incident,
not just a bug. Report it the same way as a security incident
(`docs/INCIDENT_RESPONSE.md`) with the case's model version, the doctor's
override/outcome record if one exists, and the specific input vector —
this is exactly what the provenance and outcome-recording fields above
exist to make possible. There is currently no automated adverse-event
detection (that requires real deployment volume and a real reporting
channel neither of which exist yet); this section documents the intended
process ahead of that infrastructure existing.

## What "clinically validated" would actually require (not done, not claimed)

Documented here so the gap is never quietly forgotten:

1. A real, de-identified outcome dataset of meaningful size (the outcome
   loop above is the collection mechanism, not a dataset itself yet).
2. `scripts/validate_against_dataset.py` (a skeleton, not a validated run)
   run against that dataset, with results published as an update to
   `MODEL_CARD.md` — not folded into the synthetic-data metrics.
3. An actual CDSCO classification exercise (or the equivalent for whatever
   jurisdiction VitalNet is deployed in) conducted with qualified regulatory
   counsel, not inferred from this document.
4. Institutional Ethics Committee / clinical-site sign-off appropriate to
   the deployment context, before any real-patient use beyond a controlled
   pilot with informed consent.

None of the above can be completed by an autonomous coding pass — they
require real data, real institutional review, and real legal engagement.
This document exists so that gap is explicit and trackable rather than
implied away by a growing feature list.
