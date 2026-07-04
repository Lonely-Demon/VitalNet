# Fix Log: R3-DEVOPS-DR-R3-005

- **Unit ID:** R3-DEVOPS-DR-R3-005
- **Title:** ML recovery procedure rebuilds a different artifact than runtime expects
- **Status:** completed

## Remediation

Aligned training/recovery script output with runtime artifact path by updating retrain script to save
`enhanced_triage_classifier.pkl` at the exact location expected by `classifier.py`.

Also updated script docs to reference the enhanced classifier pipeline.

## Files Modified

- `backend/scripts/retrain_and_export.py`
