# Fix Log: R3-DEVOPS-DR-R3-006

- **Unit ID:** R3-DEVOPS-DR-R3-006
- **Title:** DR scope excludes unsynced offline submissions, creating unrecoverable edge data loss
- **Status:** completed

## Remediation

Strengthened queue sync handling and observability around unsynced/failed submissions:

- Failed permanent sync items are moved to a dedicated failed queue for recovery workflows.
- Queue/failure events are surfaced for operational handling.
- DR runbook updated to include post-restore verification patterns that account for edge queue reconciliation.

## Files Modified

- `frontend/src/lib/offlineQueue.js`
- `frontend/src/stores/syncStore.js`
- `docs/DISASTER_RECOVERY.md`
