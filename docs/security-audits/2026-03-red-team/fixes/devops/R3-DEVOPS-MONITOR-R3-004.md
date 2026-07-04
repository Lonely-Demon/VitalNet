# Fix Log: R3-DEVOPS-MONITOR-R3-004

- **Unit ID:** R3-DEVOPS-MONITOR-R3-004
- **Title:** LLM tier usage is persisted as `unknown`, eliminating degradation visibility
- **Status:** completed

## Remediation

Implemented explicit LLM tier attribution and persistence:

- Set `_model_used` for each successful Groq/Gemini tier path
- Persist `llm_model_used` and `llm_status` during background enrichment
- Added fallback persistence behavior for failed enrichment paths

## Files Modified

- `backend/app/services/llm.py`
- `backend/app/api/routes/cases.py`
