# Fix Log: R3-ML-FALLBACK-R3-001

## Issue Solved
Fallback advice now escalates conservatively for urgent/emergency cases.

## Fix Applied
Made the fallback briefing severity-aware with emergency/urgent action sets.

## Files Changed
- backend/app/services/llm.py

## Verification
- Backend compile passed
