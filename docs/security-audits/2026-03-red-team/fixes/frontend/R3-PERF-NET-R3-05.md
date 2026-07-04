# Fix Log: R3-PERF-NET-R3-05

## Issue Description
The Dashboard pagination was dropping the cursor state, causing repeated page-1 fetches instead of proper cursor-based pagination. The issue was that when loading more cases, the application was not properly passing both the time cursor and priority cursor to maintain proper pagination state.

## Root Cause
The frontend code was not correctly handling the composite cursor (both time and priority) required by the backend API. The backend API returns both `nextCursor` (time-based) and `nextTriagePriority` (priority-based) values, but the frontend was only using one parameter.

## Solution Applied
1. Added missing state variable `nextTriagePriority` to track the second part of the composite cursor
2. Fixed the `loadMore` function to pass both cursor parameters to the API
3. Fixed the cursor handling to properly use both the time and priority cursors for pagination

## Files Changed
- `frontend/src/pages/Dashboard.jsx` - Main dashboard component with pagination logic
- `frontend/src/api/cases.js` - API client functions

## Verification
The fix ensures that when users click "Load More", they get the next page of results rather than repeating the first page. This was verified by checking:
1. The cursor values are properly passed between pages
2. The pagination maintains proper state between requests
3. The API correctly returns subsequent pages rather than repeating the first page

## Performance Impact
This fix resolves the issue where repeated first-page fetches were occurring, which was causing unnecessary server load and poor performance when viewing large datasets.