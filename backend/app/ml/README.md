# VitalNet Triage Classifier — Architecture & Clinical Grounding

This document explains how the ML triage classifier works, what it is
trained on, why it is designed the way it is, and — critically — its
limitations. Read this before touching `classifier.py`, `clinical_features.py`,
or `backend/scripts/train_classifier.py`.

## What it is

A single `sklearn.ensemble.HistGradientBoostingClassifier`, trained on 45
engineered clinical features, that predicts one of three triage tiers:
`ROUTINE`, `URGENT`, `EMERGENCY`. It is:

- **The only classifier in the app.** It is exported from one training run to:
  `app/ml/models/triage_classifier.pkl` (loaded by the FastAPI backend, bundled
  with a `shap.TreeExplainer` for real explanations) and
  `frontend/public/models/triage_trees.json` (loaded by the browser and walked
  by a **dependency-free pure-JS tree evaluator** —
  `frontend/src/utils/treeEvaluator.js` — for offline/local inference; there is
  **no onnxruntime-web WASM** anymore). Because both come from the same training
  run, online and offline triage can never disagree for the same input — a
  golden-vector parity test (`npm run test:parity`) enforces this. (ONNX is
  still produced in-memory during training as the intermediate the tree JSON is
  extracted from, but it is not shipped.) See `backend/CLASSIFIER_CHANGELOG.md`.
- **Abstention-aware.** Predictions carry a `low_confidence` flag (top-class
  probability < 0.55 or top-two margin < 0.15) surfaced in the UI as "model
  uncertain — clinician review recommended." Calibration is measured (ECE) at
  training time and reported in `MODEL_CARD.md`.
- **NEWS2 concerning-vital floor.** Beyond the extreme-vital safety net below,
  `classifier.py::_news2_concerning_vital` guarantees a concerning single vital
  (NEWS2 single-parameter score ≥ 2, e.g. SpO2 ≤ 92, HR ≥ 120) is never left as
  ROUTINE — it floors to URGENT. Mirrored in the JS path.
- **Explainable.** Every non-safety-net prediction is accompanied by a real
  SHAP (`TreeExplainer`) feature attribution for the model's own predicted
  class, translated into a short clinical-language sentence
  (`classifier.py::_generate_shap_explanation`). This is not a heuristic
  rule engine describing what it "probably" used — it is the model's actual
  decision decomposed feature-by-feature.
- **Backed by a deterministic safety net.** Independent of the trained
  model's own prediction, `classifier.py::_safety_net_check` force-escalates
  to `EMERGENCY` for unambiguous, extreme presentations: critically low SpO2
  (<85%), extreme heart rate (<35 or >170 bpm), extreme systolic BP (<70 or
  >220 mmHg), extreme temperature (>41.5°C or <33°C), neonatal fever, a
  hypertensive-crisis + neurological-symptom combination, or any of the
  "always-critical" symptoms (altered consciousness, seizure, severe
  bleeding, facial/throat swelling). This guarantees these specific cases
  are never missed regardless of any residual ML error — it is a hard rule,
  not a statistical hope.

## Feature engineering

`clinical_features.py::ClinicalFeatureEngineer` expands the ~14 raw intake
fields (age, sex, vitals, symptoms, free-text complaint/duration/location/
conditions) into 45 features across five groups: basic vitals/symptoms,
vital-derived scores (shock index, pulse pressure, MAP, cardiac/respiratory/
hemodynamic/sepsis risk scores, pediatric/geriatric/pregnancy adjustments),
symptom-interaction clusters, age-specific risk scores, and contextual
factors (time of day, season, location-derived healthcare access proxy).

**This logic is duplicated in JavaScript** in
`frontend/src/utils/triageClassifier.js::buildFeatureMap()` for offline
inference, since a browser cannot run scikit-learn. If you change
`ClinicalFeatureEngineer`, you must port the equivalent change to the JS
file and re-run `train_classifier.py` — there is currently no automated
cross-language test that catches drift here (see `FEATURES_ROADMAP.md` for
a proposed fix: a golden-vector parity test run in CI).

## How the synthetic training data is generated and labelled

VitalNet has no access to real de-identified patient records — rural PHC
data of this kind is not available for training. `train_classifier.py`
therefore generates a large synthetic dataset (36,000 patients, class
balanced) using two **decoupled** steps:

1. **Generation**: patients are sampled across a five-band severity
   spectrum (healthy → mild → moderate → severe → critical) with
   physiologically *correlated* vitals per band (e.g. shock generates low
   BP + high HR together, not independently — this gives the classifier
   real multi-feature syndromes to learn, not just independent per-feature
   thresholds).
2. **Labelling**: the TRUE label is computed independently by
   `assign_triage_label()`, an evidence-informed scoring function, **not**
   trusted from the generation band. A patient generated in the "severe"
   band that happens to roll mild vitals is correctly labelled
   ROUTINE/URGENT, not forced to EMERGENCY. This avoids the classifier
   learning generation-bucket artifacts instead of real vital-sign
   relationships.

`assign_triage_label()` is loosely modelled on three established clinical
scoring frameworks, adapted to the six vitals VitalNet's intake form
actually collects (no respiratory rate, no O2 supplementation status):

- **NEWS2** (Royal College of Physicians, 2017): aggregate early-warning
  scoring — score each vital 0-3 by deviation from normal, sum to an
  aggregate, and treat any single severely deranged parameter as automatic
  escalation regardless of the aggregate ("red score" rule).
- **qSOFA** (Sepsis-3, Singer et al. 2016): altered mentation + systolic BP
  ≤100 as sepsis-deterioration signals.
- **Paediatric reference ranges** (APLS/PALS-style age-banded heart rate
  and fever thresholds), since adult NEWS2 bands are invalid for a 2-year-old.
- **A deliberate departure from NEWS2** on blood pressure: NEWS2's systolic
  BP band treats the entire 111-219 mmHg range as "0" because NEWS2 targets
  acute deterioration, where *hypo*tension is the dangerous direction. That
  underweights hypertensive crisis, a distinct emergency pathway relevant to
  this population — see `_bp_sys_score` and the `hypertensive_neuro_emergency`
  rule in `train_classifier.py` for the adaptation.

**This is a heuristic label generator for a synthetic training set, not a
validated clinical scoring instrument.** It has not been through clinical
trial validation, IRB review, or regulatory clearance. It is a best-effort,
evidence-informed approximation used because no real training data exists.
Treat model outputs the same way the app's own disclaimer already frames
LLM briefings: decision support for a qualified health worker, never a
diagnosis, never a replacement for clinical judgment.

## Current performance (v3.0.0)

Held-out 5,400-sample test set and 5-fold CV on 36,000 samples:

- Accuracy: 98.9% held-out / 99.2% CV
- EMERGENCY recall (model alone): 98.3% held-out / 98.6% CV
- Expected Calibration Error: 0.0016
- Model size: ~5.7 MB (`.pkl`, carries the SHAP explainer), ~1 MB
  (`triage_trees.json`, gzips far smaller)

The model-alone EMERGENCY false negatives are borderline URGENT/EMERGENCY cases;
the deterministic safety net + NEWS2 floor escalate the unambiguous critical
subset regardless of the model, and the `low_confidence` flag + mandatory human
review cover the ambiguous ones. **These numbers are against the synthetic label
generator, not real clinical outcomes.** Full metrics, confusion matrix, and the
honest limitations statement live in `MODEL_CARD.md`.

## Regenerating the model

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt -r requirements-train.txt
python scripts/train_classifier.py
```

Always commit the regenerated `.pkl`, `triage_trees.json`, `features_config.json`,
and `golden_vectors.json` together — they must come from the same run. Never
hand-edit or partially regenerate them. After a `clinical_features.py` change,
also mirror the change in `frontend/src/utils/triageClassifier.js` and re-run
`npm run test:parity` (it will fail if the JS offline path desyncs).

**Separately**, after any `clinical_features.py` change, regenerate the
feature-level golden fixture: `python scripts/export_golden_vectors.py`
(writes `tests/fixtures/golden_feature_vectors.json`; copy it to
`frontend/tests/fixtures/` too), then run `npm run test:feature-parity`. This
is a finer-grained parity check than `test:parity` — it catches a
`buildFeatureMap()`/`ClinicalFeatureEngineer` divergence in a single named
feature, even when the final triage tier happens to land the same. It has
already caught one real bug: `buildFeatureMap()` was gating several age-band
risk scores (adult cardiac, pediatric fever, obstetric/pregnancy) on a
clamped-to-40 age value, so a real newborn (age 0) was silently scored as a
40-year-old adult in the offline path only — CI now fails immediately if this
class of bug recurs.

## Fairness audit and drift monitoring (operator-run, not scheduled)

Two diagnostic scripts, neither wired into CI or a schedule — each prints a
report for a human to read; neither takes automatic action.

```bash
# Subgroup performance (age band × sex) on a fresh synthetic evaluation set,
# run through the FULL pipeline (safety net + model + NEWS2 floor):
PYTHONPATH=. python scripts/fairness_audit.py [--n 6000] [--flag-gap 0.10]

# Feature-distribution drift (Population Stability Index) between the
# synthetic training distribution and live case_records — needs a real
# Supabase project configured (SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY):
PYTHONPATH=. python scripts/drift_monitor.py [--reference-n 4000] [--live-n 500] [--since-days 90]
```

Both are **synthetic-data diagnostics**, not real-world bias/drift audits —
VitalNet has no real patient data to check either against (see
`MODEL_CARD.md`'s training-data caveat). `fairness_audit.py` tells you
whether the model behaves consistently across the synthetic generator's
age/sex distribution (a large gap would mean the model learned some
age/sex-correlated shortcut, worth understanding before trusting it on any
subgroup). `drift_monitor.py` tells you whether the population VitalNet is
*actually seeing* has drifted from what the model was trained on. Re-run
both whenever the model is retrained
(`scripts/retrain_from_outcomes.py`) or before a real deployment — see
`docs/CLINICAL_GOVERNANCE.md`'s model lifecycle governance section.

## Why scikit-learn is pinned exactly (not `>=`)

A trained `.pkl` is only guaranteed to unpickle correctly with the exact
scikit-learn version (or a very close one) that trained it — internal
module paths change between releases. `requirements.txt` pins
`scikit-learn==1.9.0` for this reason. If you bump this version, you
**must** re-run `train_classifier.py` and commit the regenerated model in
the same change, or the backend will crash at startup
(`load_classifier()` raises `RuntimeError`). This is not hypothetical: an
earlier version of this repository shipped a `.pkl` trained on an older
scikit-learn that failed to load (`ModuleNotFoundError: No module named
'_loss'`) once a newer scikit-learn was installed from an unpinned
`>=1.5.2` constraint — a live startup-crashing bug found and fixed during
the audit that produced this document.
