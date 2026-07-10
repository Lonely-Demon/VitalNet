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

Read alongside: `MODEL_CARD.md` (what the model is), `CLINICAL_GOVERNANCE.md`
(regulatory posture), `docs/SECURITY.md` (technical security), and
`docs/VALIDATION_PROTOCOL.md` (how the open residual risks get closed).

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

## 3. Empirical basis — how far the model deviates from its own rule

VitalNet's model is trained to reproduce a deterministic, evidence-informed
scoring heuristic (`scripts/train_classifier.py::assign_triage_label`, modelled
on NEWS2 / qSOFA / PALS). Because no real ground truth exists, the most
meaningful thing we *can* measure is how often, and in which direction, the
learned model departs from that transparent rule. Any departure in the
under-triage direction is an **unvalidated** de-escalation.

Ablation (`backend/scripts/ablation_model_vs_rule.py`, 60,000 fresh
out-of-sample synthetic patients, seed ≠ training seed; rule-label mix
20,837 ROUTINE / 22,945 URGENT / 16,218 EMERGENCY):

| Comparison | Agreement | Over-triage (safe, model > rule) | **Under-triage (unsafe, model < rule)** |
|---|---|---|---|
| **Raw model** (`clf.predict`) | 98.65% | 0.61% (367) | **0.73% (441)** |
| **Production** (safety net + NEWS2 floor + model) | 92.32% | 7.36% (4,418) | **0.32% (191)** |

Under-triage breakdown, production path: EMERGENCY→ROUTINE (two-tier miss vs
rule) **8**; EMERGENCY→URGENT **122**; URGENT→ROUTINE **61**. Of the 441
raw-model under-triages, the deterministic safety net + NEWS2 floor rescue
**250**; **191 survive into production**. Of 16,218 rule-EMERGENCY cases,
**130 (0.80%)** ship below EMERGENCY.

Two things stand out. **(1)** The raw model reproduces the rule 98.65% of the
time — it is largely a *distillation* of the heuristic, adding little net-new
signal. **(2)** At the raw level its **unsafe deviations slightly exceed its
safe ones** (0.73% vs 0.61%): the "generalization" beyond the rule is, on this
measure, net-negative in the safety direction. The guardrails do real work
(they rescue 250 under-triages and add a 7.36% conservative over-triage
margin), but **191 cases — including 8 two-tier EMERGENCY→ROUTINE drops — still
ship triaged *below* what the transparent evidence-based rule would assign,
with no validated justification.**

*Caveat, stated plainly:* this measures deviation from the *heuristic*, not from
real outcomes. Some model under-triages might be more correct than the rule —
but there is no way to know without real ground truth, and in a safety-critical
setting an unexplainable de-escalation below an evidence-based rule is not
acceptable on faith. That is the argument for rules-primary until validated.

**Interpretation.** The deterministic safety net + NEWS2 floor rescue the
*unambiguous* subset of the model's under-triage deviations, but the
model-vs-rule departures that survive into production are, by construction,
**unvalidated** — there is no evidence they are improvements rather than
regressions. This is the central argument for the *rules-primary / ML-advisory*
architecture proposed in the audit: a transparent rule is auditable and
clinician-reviewable; the model's marginal deviations are neither, yet.

## 4. Hazard analysis table

Mitigations are cited to source so the safety case is traceable. Residual
risk assumes the mitigations are in place and working.

| # | Hazard | Cause(s) | Harm (Sev) | Pre-mit. likelihood | Mitigations (traced) | Residual |
|---|---|---|---|---|---|---|
| H1 | **Under-triage of a true emergency** (EMERGENCY→URGENT/ROUTINE) | Model error; the *heuristic label itself* is wrong for a real presentation; out-of-distribution case | S4 | Occasional | Deterministic safety net for extreme vitals/critical symptoms (`classifier.py::_safety_net_check`); NEWS2 concerning-vital floor (`_news2_concerning_vital`); EMERGENCY-weighted class weights `{0:1,1:2,2:7}`; mandatory doctor review; `low_confidence` abstention flag | **S4 / UNQUANTIFIED** — guardrails catch the unambiguous subset only; real-world miss rate unknown → **blocks deployment** |
| H2 | **Synthetic-data validity gap** — real performance ≠ synthetic metrics | Model learned a self-authored heuristic on self-generated patients; no real patients seen | S4 | Probable (that real ≠ synthetic) | Honest model card; metrics never claimed as real-world; outcome-feedback loop scaffolding (`FEATURES_ROADMAP §1.3`) | **S4 / UNQUANTIFIED** — the dominant open risk; only real data closes it |
| H3 | **Automation bias** — reviewer rubber-stamps a confident ROUTINE + fluent LLM briefing | Persuasive SHAP prose + LLM briefing; time pressure; over-trust | S4 | Occasional | Fixed non-removable disclaimer; `needs_review` surfacing; triage tier shown with provenance | **S3–S4 / UNQUANTIFIED** — human-factors validation not yet done |
| H4 | **Fragile free-text features** — negation-blind keyword matching | `clinical_features.py::_map_complaint_to_risk` / `_calculate_comorbidity_risk` do substring matching ("no chest pain" → chest-pain risk; spelling/Hindi/Tamil misses) | S3 | Probable | Model is primarily vitals/structured-symptom driven; free-text is a minor feature | **S2–S3 / Occasional** — fixable now (see Validation Protocol P0) |
| H5 | **Inequity / bias** — geography baked into individual triage | `_geographic_disease_risk` / `_healthcare_access_score` apply a risk multiplier from a location *string*, independent of the patient's physiology | S3 | Occasional | Small feature weight; documented | **S2–S3 / UNQUANTIFIED** — real subgroup performance unknown; equity review pending |
| H6 | **Missing vitals under-scored** — unmeasured danger invisible | No BP cuff / pulse-ox in the field; scorer treats a missing vital as 0 | S4 | Probable (rural reality) | Trained on missing-vital patterns; LLM briefing flags what was not recorded; doctor sees blanks | **S3 / Occasional** — inherent to the data-collection reality, not fully closable in software |
| H7 | **Online/offline triage divergence** | Two runtimes (Python pkl vs JS tree evaluator) drift | S4 | Remote | Golden-vector + feature + safety-net parity tests in CI (`.github/workflows/ci.yml`) | **S4 / Improbable** — well-controlled; keep the parity gates |
| H8 | **Model/data drift over time** on real inputs | Population/seasonality shift after deployment | S3 | Probable post-deployment | `scripts/drift_monitor.py` scaffolding | **S3 / UNQUANTIFIED** — monitor exists but has no real ground truth to alarm on |
| H9 | **LLM briefing hallucination** misleads clinician | LLM invents a differential/action | S3 | Occasional | Triage tier hard-locked post-generation (`llm.py::_enforce_schema`); prompt-injection sanitisation; fixed disclaimer; fallback briefing | **S2–S3 / Occasional** — tier is protected; briefing *prose* remains unvalidated |
| H10 | **Triage record tampering** post-submission | `case_records` UPDATE RLS does not restrict columns (see red-team audit finding #1) | S3 | Occasional | App-layer authz + audit log (but bypassable via direct PostgREST) | **S3 / Occasional** — cross-referenced to the security audit; fix pending |
| H11 | **Model fails to load** → no triage | Corrupt pkl / sklearn version mismatch | S2 | Remote | Fail-safe: rules-based fallback boot (`main.py` lifespan); health check reports degraded | **S1–S2 / Improbable** — fail-safe direction, good |

## 5. Risk-benefit & the deployment gate

At the current stage the **benefit** (prioritisation support for an
over-stretched ASHA/PHC workflow, with deterministic emergency guardrails) is
real, but the **residual S4 hazards H1–H3 and H6 are UNQUANTIFIED**. Under the
acceptability rule in §2, that means: **acceptable as a supervised
decision-support prototype with a human reviewing every case; NOT acceptable
as an autonomous or unsupervised real-patient device.** The gate to change
that verdict is real-world evidence, per `docs/VALIDATION_PROTOCOL.md`.

## 6. Traceability & maintenance

- Each hazard should trace forward to a test and/or a monitoring signal.
- Re-review this file on any change to `clinical_features.py`, `classifier.py`,
  `train_classifier.py`, the safety net, or the intended-use statement.
- This file is versioned with the model; record the `model_version` it was
  last reviewed against below.

_Last reviewed against model_version: 3.1.0._
