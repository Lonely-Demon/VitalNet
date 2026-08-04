# VitalNet Triage Classifier — Model Card

_Model version: 3.0.0. This card documents what the model is, how it was built,
what its metrics do and do not mean, and its limitations. Read it before relying
on, extending, or citing the model. For the architecture and training rationale,
see `README.md` in this directory; for regeneration, see
`backend/scripts/train_classifier.py`._

## Intended use

**Decision support only, for a qualified health worker.** VitalNet triages a
patient into ROUTINE / URGENT / EMERGENCY to help an ASHA (community health)
worker and a PHC doctor prioritise. It is **not** a diagnosis and **not** a
replacement for clinical judgment. Every output is framed to the user as
preliminary and reviewable, and the LLM briefing carries a fixed,
non-removable disclaimer.

**Not intended for:** autonomous clinical decisions, use without a human
reviewer, populations or care settings materially different from rural Indian
primary care, or as a validated medical device. It has **no** regulatory
clearance (CDSCO/CE/FDA) and has not undergone clinical trial validation.

## Model

- **Type:** a single `sklearn.ensemble.HistGradientBoostingClassifier`
  (gradient-boosted decision trees), 3 classes, on **43 engineered clinical
  features** (`app/ml/clinical_features.py`).
- **One model, two runtimes:** the same trained model runs server-side (Python,
  from `triage_classifier.pkl`, with a bundled SHAP `TreeExplainer` for
  per-patient explanations) and in the browser for offline triage (as
  `frontend/public/models/triage_trees.json`, evaluated by a dependency-free JS
  tree walker — no onnxruntime). A golden-vector parity test enforces that the
  two produce identical classifications.
- **Deterministic safety layers wrap the model** (see `app/ml/classifier.py`):
  a **safety net** force-escalates unambiguous extreme presentations (SpO2 < 85,
  HR < 35 / > 170, systolic BP < 70 / > 220, temp > 41.5 / < 33, neonatal fever,
  hypertensive crisis + neuro symptoms, and the always-critical symptoms) to
  EMERGENCY independent of the model; a **NEWS2 concerning-vital floor** never
  lets a concerning single vital (NEWS2 single-parameter score ≥ 2) remain
  ROUTINE. These are guarantees by construction, not model predictions.
- **Abstention:** a `low_confidence` flag is raised when the top-class
  probability < 0.55 or the top-two margin < 0.15, and surfaced in the UI as
  "model uncertain — clinician review recommended."
- **Contextual features are now all real signals.** A prior round's audit
  found that `time_of_day_risk`, `epidemic_alert_level`, and the old
  `geographic_risk`/`seasonal_risk` placeholders were constant (or
  effectively constant) across the entire training set — `datetime.now()`
  runs once per training script invocation, so every one of the 36,000
  training patients got the same value, and a gradient-boosted tree can
  never learn a split on a constant feature. These contributed **zero**
  influence on any prediction despite being computed on every request.
  `time_of_day_risk`/`epidemic_alert_level` were removed outright (43
  features, down from 45); `seasonal_risk`/`geographic_risk` were rebuilt as
  real signals — `scripts/train_classifier.py` now samples a
  `_reference_month` per synthetic patient and correlates monsoon-season
  (June–September) + rural/tribal location with a real dengue/malaria-like
  symptom-probability bump, so the model has genuine training-time variance
  and a real label correlation to learn from. See `docs/DECISIONS.md` §23.

## Training data — synthetic, evidence-informed (important caveat)

The project has **no access to real de-identified patient data**. Training data
is **synthetic**: 36,000 physiologically-correlated patients (class-balanced),
labelled by an evidence-informed scoring function decoupled from generation (so
the label reflects the actual synthesised physiology, not the generation
bucket). The scorer is loosely modelled on **NEWS2** (aggregate + any-red-
parameter escalation), **qSOFA** (deterioration), and **paediatric APLS/PALS**
vital-sign reference ranges, with a deliberate hypertensive-crisis extension.
The generator also simulates the rural reality of **missing vitals** (no BP
cuff / pulse-ox on ~6–28% of samples per vital) and a few edge syndromes (silent
MI / atypical presentation, sepsis-without-fever). Full details and the exact
thresholds: `app/ml/README.md` and `scripts/train_classifier.py`.

> **What the metrics below mean — and don't.** Accuracy is measured against the
> synthetic label generator. It quantifies *how faithfully the model learned the
> evidence-based scoring heuristic*, **not** performance against real clinical
> outcomes. Do not read "98.9% accuracy" as "98.9% correct on real patients." No
> claim of parity with clinically-validated triage instruments is made or
> implied. Real-world validation requires real outcome data — the outcome-
> feedback loop in `FEATURES_ROADMAP.md` (§1.3) is the path to it.

## Performance (held-out synthetic test set, v3.0.0)

Held-out test set: 5,400 samples (15% split). 5-fold stratified CV on all 36,000.

| Metric | Value |
|---|---|
| Accuracy (held-out) | 99.0% |
| Accuracy (5-fold CV) | 99.1% |
| EMERGENCY recall — model alone (held-out) | 98.8% |
| EMERGENCY recall — model alone (CV) | 98.5% |
| Expected Calibration Error (ECE, 10-bin, class-balanced set) | 0.0020 |

Held-out confusion matrix (rows = true ROUTINE/URGENT/EMERGENCY):

```
        pred:  ROUTINE  URGENT  EMERGENCY
ROUTINE         1800       0        0
URGENT             9    1769       22
EMERGENCY          3      18     1779
```

**On the 21 model-alone EMERGENCY false negatives:** these are borderline cases
the model placed in URGENT/ROUTINE. The deterministic safety net + NEWS2 floor
run *on top of* the model at inference time and guarantee EMERGENCY for the
**unambiguous** critical subset (extreme vitals, critical symptoms) and at least
URGENT for any concerning vital — so a patient with a genuinely extreme
presentation is escalated regardless of the model. The residual borderline
cases are exactly where the `low_confidence` flag and the mandatory human review
are the safeguard. **We do not claim zero missed emergencies on real patients** —
we claim a layered design where the unambiguous cases are caught deterministically
and the ambiguous ones are flagged for a clinician.

**Calibration:** ECE of 0.0020 on the class-balanced test set indicates the raw
boosted-tree probabilities are already well-calibrated on *that* distribution, so
no post-hoc calibration transform is applied (it would also have to be mirrored
exactly in the JS offline evaluator to preserve parity). The abstention flag is
the shipped uncertainty mechanism.

**Realistic-prevalence validation (new):** the class-balanced ECE above measures
calibration against an even 33/33/33 class split, which is *not* the distribution
VitalNet sees in the field (mostly ROUTINE). `scripts/train_classifier.py`
separately subsamples the same held-out test set down to a **~85% ROUTINE / 12%
URGENT / 3% EMERGENCY** realistic prevalence (n=2,117: 1,800 ROUTINE / 254 URGENT
/ 63 EMERGENCY) and re-measures ECE and the `low_confidence` abstention rate
against it — validating the *same fixed* 0.55-probability / 0.15-margin
thresholds under the deployment-shape distribution, not just the training
distribution. Result: accuracy 99.8%, ECE 0.0050 (still low, though roughly 2.5x
the balanced-set figure — expected, since a model this confident on the dominant
ROUTINE class naturally shows a slightly larger absolute calibration gap when
that class dominates the sample), abstention rate 0.0% (the model was never
uncertain on this particular realistic-prevalence sample — a genuinely easy
regime for a model this accurate, not evidence the abstention mechanism is
broken; it fires on the harder borderline cases the balanced test set surfaces
proportionally more of).

## Known limitations

- Synthetic training data (above) — the dominant limitation.
- Free-text (chief complaint, observations) is only lightly used via keyword
  features; the model is vitals- and structured-symptom-driven.
- No respiratory rate or supplemental-O2 status (not collected by the intake
  form), so the NEWS2 approximation omits those parameters.
- Trained for rural Indian primary care; not validated elsewhere.
- The safety net's + NEWS2 floor's paediatric thresholds are intentionally
  conservative and NOT age-adjusted (they must stay dead-simple and mirror
  1:1 in JS): a normal infant's HR ~140 or systolic BP ~85 can be floored to
  URGENT by the adult NEWS2 bands. This is mild over-triage in the safe
  direction (never EMERGENCY, never a missed escalation) — an accepted
  tradeoff, unchanged in v3.1.0.
- **Model-level infant over-triage — FIXED in v3.1.0** (was a documented
  limitation in v3.0.0): a hemodynamically normal infant (e.g. 6-month-old,
  HR 140, BP 85/55 — all normal for age) was previously escalated to
  EMERGENCY by the *model's own judgment* because (a) the synthetic-label
  scorer age-adjusted HR and temperature but **not systolic BP**, so a normal
  infant's low-for-adult BP scored as "hypotension" and the label itself said
  EMERGENCY, and (b) infants were only ~1.7% of the training set. v3.1.0 adds
  an age-banded paediatric BP scorer (PALS 5th-percentile hypotension
  thresholds), age-appropriate BP generation, an age-gated qSOFA hypotension
  criterion, and ~22% paediatric oversampling. That exact case now classifies
  URGENT (the conservative floor), not EMERGENCY, while genuinely sick
  children (frank hypotension for age, SpO2 84, neonatal fever) still escalate
  correctly. See `docs/DECISIONS.md` §31.
- **Altitude over-triage — still a documented limitation** (not fixable
  without an altitude field): an asymptomatic chronic high-altitude resident
  with baseline SpO2 ~88% is escalated (URGENT by the floor, sometimes
  EMERGENCY by the model). Without an altitude/baseline-SpO2 input the app
  cannot distinguish adapted chronic hypoxia from acute hypoxia, and treating
  an isolated SpO2 of 88 as concerning is the clinically safe default. A
  future `baseline_spo2` or altitude field would resolve it.
- **No monotonic constraints (considered, currently infeasible):** several
  engineered features are constructed as unambiguous "higher = worse" scores
  (`shock_index`, `sepsis_risk_score`, `hemodynamic_instability`,
  `respiratory_distress_score`, `cardiac_risk_score`), and constraining the
  model to respect that monotonically would make behavior in sparse/
  out-of-distribution feature-space provably safe rather than merely
  probable. Verified directly: `HistGradientBoostingClassifier` in the pinned
  scikit-learn 1.9.0 raises `ValueError: monotonic constraints are not
  supported for multiclass classification` for this 3-class problem — not
  implemented here to avoid an unplanned scikit-learn upgrade. Worth
  revisiting if/when the pin moves.

## Ethical & safety considerations

- **Human-in-the-loop by design:** a doctor reviews every case; the ML triage is
  never the final actor.
- **Fail-safe direction:** all deterministic overrides escalate (never de-
  escalate); the offline path falls back to rules if the model can't load, so
  triage never silently fails.
- **Transparency:** SHAP explanations accompany model predictions; safety-net /
  floor escalations state their deterministic reason.
- **Contraindication flags are advisory, not comprehensive:**
  `app/ml/contraindications.py` checks a small curated list of free-text
  keyword matches (see `docs/DECISIONS.md` §17) — it never changes the
  triage tier, only forces `needs_review`, and does not attempt general
  drug-drug interaction checking (no structured drug database exists here).
- **No PII in logs:** validation errors are scrubbed of input values
  (`app/main.py`).
- **Fairness and drift monitoring:** `scripts/fairness_audit.py` (subgroup
  accuracy/EMERGENCY-recall by age band and sex) and `scripts/drift_monitor.py`
  (feature-distribution drift, live data vs. training distribution) are
  operator-run diagnostics — see `README.md`'s "Fairness audit and drift
  monitoring" section. Both are synthetic-data checks, same caveat as the
  metrics above; neither is a substitute for real-world validation.

## Regenerating / changing the model

`cd backend && pip install -r requirements.txt -r requirements-train.txt &&
python scripts/train_classifier.py`. This retrains and re-exports the `.pkl`,
`triage_trees.json`, `features_config.json`, and the golden-vector fixture from
one run, and asserts py-pkl == onnx == tree-JSON parity. If you change
`clinical_features.py`, mirror it in `frontend/src/utils/triageClassifier.js` and
re-run — the frontend parity test (`npm run test:parity`) will fail otherwise.
Never bump `scikit-learn` without retraining in the same change (see
`app/ml/README.md`).
