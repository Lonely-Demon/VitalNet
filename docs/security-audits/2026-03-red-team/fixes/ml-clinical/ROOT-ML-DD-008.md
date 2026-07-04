# Fix Log: ROOT-ML-DD-008

## Issue Solved
Human override is now explicitly represented in the intake flow.

## Fix Applied
Added a human-review checkbox and review-reason field to the intake form and persisted those flags with the case record.

## Files Changed
- frontend/src/pages/IntakeForm.jsx
- backend/app/models/schemas.py
- backend/app/api/routes/cases.py

## Verification
- Frontend build passed
- Backend compile passed
