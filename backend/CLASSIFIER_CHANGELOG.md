# Classifier Evolution

| Version | File | Notes |
|---|---|---|
| v1.0 | `classifier_original.py` (deleted) | Original Phase 1, basic vitals features |
| v2.0 | `classifier_v2.py` (deleted) | Second iteration, improved recall |
| v3.0 (legacy) | `classifier.py` → `_predict_legacy()` | 45-feature pipeline via `ClinicalFeatureEngineer` |
| v4.0 (enhanced) | `enhanced_classifier.py` | Multi-stage classifier, auto-loaded if `enhanced_triage_classifier.pkl` exists |
