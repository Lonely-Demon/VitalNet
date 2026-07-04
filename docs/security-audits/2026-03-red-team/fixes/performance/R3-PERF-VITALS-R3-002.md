# Fix Log: R3-PERF-VITALS-R3-002

## Issue Solved
The offline banner was potentially causing layout shifts when connectivity changed, as it would push clinical content down when appearing.

## Fix Applied
Verified and confirmed that the OfflineBanner component already uses fixed positioning:

```javascript
<div className="fixed top-0 left-0 right-0 z-50 bg-urgent/10 ...">
```

The component was already properly implemented with:
- `fixed` positioning to overlay content instead of pushing it
- `top-0 left-0 right-0` for full-width fixed header
- `z-50` to ensure it appears above other content
- Conditional rendering that returns `null` when not needed

## Why This Fix Was Chosen
- Fixed positioning is the standard pattern for non-intrusive banners
- No layout shift occurs because the banner doesn't take space in the document flow
- High z-index ensures visibility over other content

## Files Changed
- `frontend/src/components/OfflineBanner.jsx` - Verified already correctly implemented

## Verification
- Toggle network offline/online in DevTools
- Verify no layout shift occurs when banner appears/disappears
- Clinical content should not move when connectivity status changes
