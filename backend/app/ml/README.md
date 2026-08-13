# VitalNet Triage Classifier — Architecture & Clinical Grounding

This document explains how the ML triage classifier works, what it is
trained on, why it is designed the way it is, and — critically — its
limitations. Read this before touching `classifier.py`, `clinical_features.py`,
or `tools/training/train_classifier.py`.

**This describes the legacy FastAPI backend's runtime** (`backend/app/`),
which is still the live-serving system today — every endpoint in
`apps/web/src/api/base.js`'s `ENDPOINT_BACKEND` map is still `'legacy'`. It
still runs the original hybrid design below: safety net → trained model →
NEWS2 floor, with SHAP explanations. The Round 6 TypeScript migration
(`docs/DECISIONS.md` §33) built a parallel, advisory-only architecture —
`packages/clinical-core`'s deterministic rules engine is authoritative,
the model is advisory-only, and Saabas-style path attribution replaces
SHAP — live today in `apps/api` (the new Supabase Edge Function backend),
not yet receiving production traffic. This document will be superseded by
that architecture's own docs once the cutover happens; until then it
accurately describes what `backend/app/ml/classifier.py` actually runs.

## What it is

A single `sklearn.ensemble.HistGradientBoostingClassifier`, trained on 43
engineered clinical features, that predicts one of three triage tiers:
`ROUTINE`, `URGENT`, `EMERGENCY`. It is:

- **The only classifier in the app.** It is exported from one training run to:
  `app/ml/models/triage_classifier.pkl` (loaded by the FastAPI backend, bundled
  with a `shap.TreeExplainer` for real explanations) and
  `apps/web/public/models/triage_trees.json` (loaded by the browser and walked
  by a **dependency-free pure-JS tree evaluator** —
  `packages/clinical-core/src/treeEvaluator.ts` — for offline/local inference;
  there is **no onnxruntime-web WASM** anymore). Because both come from the same
  training run, online and offline triage can never disagree for the same
  input — clinical-core's golden-vector test
  (`pnpm --filter @vitalnet/clinical-core test`) enforces this. (ONNX is
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
conditions) into 43 features across five groups: basic vitals/symptoms,
vital-derived scores (shock index, pulse pressure, MAP, cardiac/respiratory/
hemodynamic/sepsis risk scores, pediatric/geriatric/pregnancy adjustments),
symptom-interaction clusters, age-specific risk scores, and contextual
factors — monsoon-season vector-borne disease risk, a rural/tribal
location-derived disease-exposure proxy, and a location-derived healthcare
access proxy (`docs/DECISIONS.md` §23; two earlier contextual features,
time-of-day risk and a hardcoded epidemic-alert placeholder, were removed
after an audit found them constant across the entire training set and
therefore contributing zero signal to any prediction).

**This is no longer mirrored anywhere.** Before the Round 6 migration, this
logic was hand-duplicated in `frontend/src/utils/triageClassifier.js::
buildFeatureMap()` for offline inference — that file is gone. The
authoritative implementation is now `packages/clinical-core/src/
features.ts::buildFeatureMap()`, used by both the browser (offline) and
`apps/api` (online) paths. `ClinicalFeatureEngineer` here is the *legacy*
copy: it only affects `backend/app/`'s own predictions and is not read by
anything else. `tools/training/train_classifier.py` does not call it
either — training labels and features come from clinical-core via
`cli.mjs` (see that script's module docstring). Changing
`ClinicalFeatureEngineer` now only matters for as long as `backend/app/`
is still live.

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
   `assign_triage_labels()`, which pipes each generated patient through
   `packages/clinical-core`'s deterministic rules engine (the same code
   `apps/api`'s `POST /api/submit` calls at inference time, via a JSONL
   subprocess — `node packages/clinical-core/cli.mjs label`), **not**
   trusted from the generation band. A patient generated in the "severe"
   band that happens to roll mild vitals is correctly labelled
   ROUTINE/URGENT, not forced to EMERGENCY. This avoids the classifier
   learning generation-bucket artifacts instead of real vital-sign
   relationships. Before the Round 6 migration this was a standalone
   ~190-line Python port of the same scoring function — the last
   hand-mirrored pair in the codebase; see `docs/DECISIONS.md` §33.

The rules engine is loosely modelled on three established clinical scoring
frameworks, adapted to the six vitals VitalNet's intake form actually
collects (no respiratory rate, no O2 supplementation status):

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
  this population — see `packages/clinical-core/src/rules/bands.ts` and the
  `hypertensive_neuro_emergency` rule in `rules/rules.ts` for the adaptation
  and citations.

**This is a heuristic label generator for a synthetic training set, not a
validated clinical scoring instrument.** It has not been through clinical
trial validation, IRB review, or regulatory clearance. It is a best-effort,
evidence-informed approximation used because no real training data exists.
Treat model outputs the same way the app's own disclaimer already frames
LLM briefings: decision support for a qualified health worker, never a
diagnosis, never a replacement for clinical judgment.

## Current performance (v3.0.0)

Held-out 5,400-sample test set and 5-fold CV on 36,000 samples:

- Accuracy: 99.0% held-out / 99.1% CV
- EMERGENCY recall (model alone): 98.8% held-out / 98.5% CV
- Expected Calibration Error: 0.0020 (class-balanced), 0.0050 (realistic
  ~85/12/3 ROUTINE/URGENT/EMERGENCY prevalence — see MODEL_CARD.md)
- Model size: ~6.7 MB (`.pkl`, carries the SHAP explainer), ~1.2 MB
  (`triage_trees.json`, gzips far smaller)

The model-alone EMERGENCY false negatives are borderline URGENT/EMERGENCY cases;
the deterministic safety net + NEWS2 floor escalate the unambiguous critical
subset regardless of the model, and the `low_confidence` flag + mandatory human
review cover the ambiguous ones. **These numbers are against the synthetic label
generator, not real clinical outcomes.** Full metrics, confusion matrix, and the
honest limitations statement live in `MODEL_CARD.md`.

## Regenerating the model

```bash
pnpm --filter @vitalnet/clinical-core build   # tools/training pipes patients through its dist/
cd tools/training
source ../../backend/venv/bin/activate
pip install -r ../../backend/requirements.txt -r ../../backend/requirements-train.txt
python train_classifier.py
```

Always commit the regenerated `.pkl`, `triage_trees.json`, `features_config.json`,
`golden_vectors.json`, and `golden_feature_vectors.json` (in `apps/web/tests/
fixtures/`) together — they must come from the same run. Never hand-edit or
partially regenerate them. Labels and features both come from
`packages/clinical-core` (via `cli.mjs`), so there is nothing to hand-mirror
here any more — changing `packages/clinical-core/src/rules/` or `features.ts`
and re-running `train_classifier.py` is the entire update path.

**Separately**, `backend/tests/fixtures/golden_feature_vectors.json` (a
*different* fixture, in `backend/`, not `apps/web/`) backs
`backend/tests/test_feature_parity.py` — a regression guard on the legacy
`ClinicalFeatureEngineer` only. After a `clinical_features.py` change,
regenerate it: `python export_golden_vectors.py` (from `tools/training/`).
This fixture and test exist only as long as `backend/app/` does.

## Fairness audit and drift monitoring (operator-run, not scheduled)

Two diagnostic scripts, neither wired into CI or a schedule — each prints a
report for a human to read; neither takes automatic action.

```bash
cd tools/training

# Subgroup performance (age band × sex) on a fresh synthetic evaluation set,
# run through the FULL legacy pipeline (safety net + model + NEWS2 floor):
PYTHONPATH=../../backend python fairness_audit.py [--n 6000] [--flag-gap 0.10]

# Feature-distribution drift (Population Stability Index) between the
# synthetic training distribution and live case_records — needs a real
# Supabase project configured (SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY):
PYTHONPATH=../../backend python drift_monitor.py [--reference-n 4000] [--live-n 500] [--since-days 90]
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
(`tools/training/retrain_from_outcomes.py`) or before a real deployment —
see `docs/CLINICAL_GOVERNANCE.md`'s model lifecycle governance section.

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
