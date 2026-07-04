# Fix Log: ROOT-ML-DD-001

## Issue Solved
Fallback LLM briefings and their parser failure path can now carry explicit review status and severity-aware emergency actions instead of silently passing as normal output.

## Fix Applied
Added uncertainty-aware schema fields, fallback escalation actions, and review flags in `backend/app/services/llm.py`, plus request/record propagation in `backend/app/api/routes/cases.py`.

## Files Changed
- backend/app/services/llm.py
- backend/app/api/routes/cases.py

## Verification
- Backend compile passed
- LLM fallback now includes `llm_status` and `needs_review`
- Case records persist review metadata
