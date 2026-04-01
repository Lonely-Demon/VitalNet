# Fix Log: ROOT-PERF-005

## Issue Solved
The BriefingCard component was re-rendering on every parent Dashboard state change, even when its own props hadn't changed. This caused unnecessary re-renders when the case list updated via realtime subscriptions.

**Bundled Source IDs**: PERF-005, PERF-RENDER-R3-004

## Fix Applied
Wrapped the BriefingCard component export with `React.memo()`:

```javascript
// Before
export default function BriefingCard({ caseData, onReviewed }) { ... }

// After
function BriefingCard({ caseData, onReviewed }) { ... }
export default React.memo(BriefingCard)
```

This prevents the component from re-rendering when its parent re-renders, unless the `caseData` or `onReviewed` props actually change.

## Why This Fix Was Chosen
- `React.memo` is the standard pattern for preventing unnecessary re-renders
- The component receives stable props that don't change frequently
- Simple change with no risk of breaking functionality
- Significant performance improvement when many cards are rendered

## Files Changed
- `frontend/src/components/BriefingCard.jsx` - Added React.memo wrapper

## Verification
After the fix:
- Open React DevTools Profiler
- Trigger a Dashboard re-render (e.g., new realtime case)
- Verify that unchanged BriefingCard instances don't re-render
- Total render time should decrease for large case lists
