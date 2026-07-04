# Fix Log: R3-PERF-VITALS-R3-003

## Issue Description
The dashboard was hiding all clinical queue UI during initial data fetch, showing only a simple "Loading cases..." message. This created a poor user experience as users saw no UI structure during the loading phase.

## Solution Applied
1. **Replaced simple loading message** with skeleton/placeholder UI that shows the structure of the dashboard during loading
2. **Added skeleton loaders** that display the layout and structure while data is being fetched
3. **Implemented progressive loading pattern** to improve perceived performance

## Why This Approach
Instead of completely hiding the UI during loading, we now show:
- The structural layout of the dashboard
- Skeleton placeholders for the clinical queue sections
- Disabled but visible UI controls
- A more responsive feeling interface

This approach was chosen over alternatives because:
1. It maintains user context by showing the UI structure
2. It provides immediate visual feedback that the app is working
3. It reduces perceived loading time by showing progress immediately
4. It follows modern web performance best practices for perceived performance

## Files Changed
- `frontend/src/pages/Dashboard.jsx` - Modified loading state to show skeleton UI instead of hiding everything
- `frontend/src/components/SkeletonCard.jsx` - Created new skeleton component for loading placeholders

## Verification
The fix improves the user experience by:
1. Showing the UI structure immediately on page load
2. Displaying skeleton loaders that match the actual content layout
3. Maintaining layout consistency between loading and loaded states
4. Providing visual feedback during data fetching

## Commands to verify
```bash
cd frontend && npm run dev
```

Then navigate to the dashboard and observe the loading state behavior.