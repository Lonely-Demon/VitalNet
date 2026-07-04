# Fix Log: R3-ML-CONF-R3-3

## Issue Solved
The LLM briefing now receives classifier uncertainty context and marks review state explicitly.

## Fix Applied
Extended the LLM patient context and schema to carry uncertainty and review metadata.

## Files Changed
- backend/app/services/llm.py

## Verification
- Backend compile passed
