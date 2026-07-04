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
  (gradient-boosted decision trees), 3 classes, on **45 engineered clinical
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
| Accuracy (held-out) | 98.9% |
| Accuracy (5-fold CV) | 99.2% |
| EMERGENCY recall — model alone (held-out) | 98.3% |
| EMERGENCY recall — model alone (CV) | 98.6% |
| Expected Calibration Error (ECE, 10-bin) | 0.0016 |

Held-out confusion matrix (rows = true ROUTINE/URGENT/EMERGENCY):

```
        pred:  ROUTINE  URGENT  EMERGENCY
ROUTINE         1799       1        0
URGENT             9    1773       18
EMERGENCY          1      29     1770
```

**On the 30 model-alone EMERGENCY false negatives:** these are borderline cases
the model placed in URGENT/ROUTINE. The deterministic safety net + NEWS2 floor
run *on top of* the model at inference time and guarantee EMERGENCY for the
**unambiguous** critical subset (extreme vitals, critical symptoms) and at least
URGENT for any concerning vital — so a patient with a genuinely extreme
presentation is escalated regardless of the model. The residual borderline
cases are exactly where the `low_confidence` flag and the mandatory human review
are the safeguard. **We do not claim zero missed emergencies on real patients** —
we claim a layered design where the unambiguous cases are caught deterministically
and the ambiguous ones are flagged for a clinician.

**Calibration:** ECE of 0.0016 indicates the raw boosted-tree probabilities are
already well-calibrated on this data, so no post-hoc calibration transform is
applied (it would also have to be mirrored exactly in the JS offline evaluator to
preserve parity). The abstention flag is the shipped uncertainty mechanism.

## Known limitations

- Synthetic training data (above) — the dominant limitation.
- Free-text (chief complaint, observations) is only lightly used via keyword
  features; the model is vitals- and structured-symptom-driven.
- No respiratory rate or supplemental-O2 status (not collected by the intake
  form), so the NEWS2 approximation omits those parameters.
- Trained for rural Indian primary care; not validated elsewhere.
- The safety net's paediatric HR floor is intentionally conservative (may
  over-triage some children to URGENT — an accepted safe-side tradeoff).

## Ethical & safety considerations

- **Human-in-the-loop by design:** a doctor reviews every case; the ML triage is
  never the final actor.
- **Fail-safe direction:** all deterministic overrides escalate (never de-
  escalate); the offline path falls back to rules if the model can't load, so
  triage never silently fails.
- **Transparency:** SHAP explanations accompany model predictions; safety-net /
  floor escalations state their deterministic reason.
- **No PII in logs:** validation errors are scrubbed of input values
  (`app/main.py`).

## Regenerating / changing the model

`cd backend && pip install -r requirements.txt -r requirements-train.txt &&
python scripts/train_classifier.py`. This retrains and re-exports the `.pkl`,
`triage_trees.json`, `features_config.json`, and the golden-vector fixture from
one run, and asserts py-pkl == onnx == tree-JSON parity. If you change
`clinical_features.py`, mirror it in `frontend/src/utils/triageClassifier.js` and
re-run — the frontend parity test (`npm run test:parity`) will fail otherwise.
Never bump `scikit-learn` without retraining in the same change (see
`app/ml/README.md`).
