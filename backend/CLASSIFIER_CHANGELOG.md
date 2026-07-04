# Classifier Evolution

| Version | File | Notes |
|---|---|---|
| v1.0 | `classifier_original.py` (deleted) | Original Phase 1, basic vitals features |
| v2.0 | `classifier_v2.py` (deleted) | Second iteration, improved recall |
| v3.0 (legacy) | `classifier.py` → `_predict_legacy()` (deleted) | 45-feature pipeline via `ClinicalFeatureEngineer` |
| v4.0 (enhanced, **retired**) | `enhanced_classifier.py` (deleted) | 4-sub-model ensemble (`emergency_detector` + `symptom_classifier` + `clinical_reasoner` + `VotingClassifier` + `CalibratedClassifierCV`). Retired because: (1) the shipped `.pkl` was empirically found to be incompatible with current scikit-learn (`ModuleNotFoundError: No module named '_loss'` on load — a live startup-crashing bug), (2) it was 25 MB and ran 3 tree models redundantly per prediction for no measurable accuracy gain over a single well-tuned model, and (3) the backend's "enhanced" model and the frontend's ONNX-exported model were trained independently on different synthetic data, so online and offline triage could disagree for the same patient. |
| v3.0.0 (unified) | `classifier.py` + `scripts/train_classifier.py` | Single `HistGradientBoostingClassifier` trained once and exported to both the backend `.pkl` and a frontend artifact — guaranteeing online and offline triage always agree. Added the deterministic safety-net override (`_safety_net_check`) escalating unambiguous critical presentations to EMERGENCY independent of the model. Evidence-informed synthetic labels (NEWS2 / qSOFA / paediatric APLS-PALS). |
| **v3.0.0 (current, round-2 hardening)** | same files + `scripts/tree_export.py`, `frontend/src/utils/{treeEvaluator,clinicalRules}.js`, `app/ml/MODEL_CARD.md` | Round-2 refinements: **(1) Offline runtime replaced** — the browser no longer loads onnxruntime-web (~12 MB WASM); the model is exported as compact `triage_trees.json` (~1 MB) and evaluated by a dependency-free JS tree walker, with a golden-vector parity test (`npm run test:parity`) asserting JS == server. **(2) NEWS2 concerning-vital floor** (`_news2_concerning_vital`) — a concerning single vital (NEWS2 score ≥ 2) can never be left ROUTINE; floors to URGENT. Mirrored in JS. **(3) Abstention** — a `low_confidence` flag (top proba < 0.55 or margin < 0.15) surfaced in the UI. **(4) Broader training** — synthetic generator now simulates missing vitals (rural no-cuff/no-pulse-ox reality) and edge syndromes (silent MI, sepsis-without-fever); 5-fold CV + ECE reporting added. **(5) Rules-only fallback** offline so triage never fails if the model can't load. Full metrics + honest limitations: `MODEL_CARD.md`. Held-out: 98.9% acc, 98.3% EMERGENCY recall (model alone), ECE 0.0016; CV: 99.2% acc.|

## Regenerating the model

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt -r requirements-train.txt
python scripts/train_classifier.py
```

This is the **only** supported training entrypoint. `colab/triage_classifiers.py` is a historical Google Colab reference script trained on only the 14 basic (non-engineered) features — it predates `ClinicalFeatureEngineer` and is not wired into the app; keep it only for historical reference, do not use its output as a production model.
