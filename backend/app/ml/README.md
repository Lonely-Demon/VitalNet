# VitalNet Triage Classifier — Architecture & Clinical Grounding

This document explains how the ML triage classifier works, what it is
trained on, why it is designed the way it is, and — critically — its
limitations. Read this before touching `classifier.py`, `clinical_features.py`,
or `backend/scripts/train_classifier.py`.

## What it is

A single `sklearn.ensemble.HistGradientBoostingClassifier`, trained on 45
engineered clinical features, that predicts one of three triage tiers:
`ROUTINE`, `URGENT`, `EMERGENCY`. It is:

- **The only classifier in the app.** It is exported to two formats from one
  training run: `app/ml/models/triage_classifier.pkl` (loaded by the FastAPI
  backend, bundled with a `shap.TreeExplainer` for real explanations) and
  `frontend/public/models/triage_classifier.onnx` (loaded by the browser via
  `onnxruntime-web` for offline/local inference). Because both come from the
  same training run, online and offline triage can never disagree for the
  same input — this was not true of the previous two-model architecture
  (see `backend/CLASSIFIER_CHANGELOG.md`).
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

## Current performance (v3.0.0, held-out 5,400-sample test set)

- Overall accuracy: ~99.4%
- EMERGENCY recall: ~99.3% (12 false negatives out of 1,800 EMERGENCY test
  cases from the model alone — the deterministic safety net catches the
  unambiguous subset of these independently of the model)
- Model size: ~4-5 MB (`.pkl`), <1 MB (`.onnx`)

These numbers describe performance against the synthetic label-generation
function, not against real clinical outcomes — read them as "how well the
model learned the scoring heuristic," not "how well it will perform on a
real patient." See `FEATURES_ROADMAP.md` for the plan to validate against
real-world outcome data once a feedback loop exists.

## Regenerating the model

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt -r requirements-train.txt
python scripts/train_classifier.py
```

Always commit the regenerated `.pkl`, `.onnx`, and `features_config.json`
together — they must come from the same run. Never hand-edit or partially
regenerate one of the three.

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
