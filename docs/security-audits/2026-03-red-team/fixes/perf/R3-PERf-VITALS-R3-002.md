# Fix for R3-PERF-VITALS-R3-002

## Issue
The offline banner was causing layout shifts when it appeared, making clinical content jump on the page.

## Solution
The issue was solved by changing the banner to use fixed positioning instead of normal document flow.

## Files Changed
- `frontend/src/components/OfflineBanner.jsx` - Changed to fixed positioning
- `frontend/src/panels/ASHAPanel.jsx` - Added top padding to accommodate the fixed banner

## Solution Details
The solution was to change the banner to use fixed positioning instead of normal document flow.

## Verification
The fix maintains layout stability by ensuring the banner uses `position: fixed` which prevents content pushing when the banner appears.