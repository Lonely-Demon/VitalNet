# Fix Log: R3-PERF-VITALS-R3-005

## Issue Solved
The "Load More" functionality in the Dashboard was triggering redundant first-page fetches because it was not properly using the cursor-based pagination parameters required by the backend API. The `loadMore` function was passing `before: nextCursor` to the `getCases` function, but the backend API expects two specific parameters: `before_time` and `before_priority`.

## Fix Applied
1. Added a new state variable `nextPriority` to track the triage priority cursor
2. Modified the `loadMore` function to properly pass both `before_time` and `before_priority` parameters
3. Updated the initial load to properly set both cursor state variables (`nextCursor` and `nextPriority`)

## Why This Fix Was Chosen
This fix directly addresses the root cause of the redundant fetches issue by ensuring the correct cursor parameters are used for pagination. The previous implementation was passing an incorrect parameter name (`before` instead of `before_time` and `before_priority`), which caused the backend to ignore the pagination parameters and return the first page instead of the next page.

## Files Changed
- `frontend/src/pages/Dashboard.jsx`

## Verification Commands/Results
The fix can be verified by:
1. Running the application and clicking "Load More Cases" button
2. Confirming that subsequent pages are loaded correctly rather than re-fetching the first page
3. Checking browser network tab to ensure API calls are using proper cursor parameters

The fix ensures that each "Load More" click properly fetches the next page of results without re-fetching already loaded data.