# ROOT-PERF-001 Fix Log

## Issue Solved
The entire VitalNet application was being loaded upfront as a single ~2MB bundle, causing slow initial load times and poor performance on low-bandwidth connections.

## Fix Applied
Implemented code splitting to reduce initial bundle size by:
1. Configured Vite's rollupOptions to create separate chunks for:
   - React and related dependencies
   - ONNX runtime as a separate chunk
   - Supabase client library
   - Utility libraries
2. Implemented React lazy loading for panel components (ASHA, Doctor, Admin panels)
3. Added Suspense boundaries for proper loading states

## Why This Approach
This fix was chosen because it:
1. Reduces initial bundle size by splitting code into smaller chunks
2. Uses Vite's built-in code splitting capabilities for optimal chunking
3. Implements React's lazy loading for route-based code splitting
4. Maintains application functionality while improving performance

## Files Changed
- `frontend/vite.config.js` - Added build.rollupOptions.manualChunks configuration
- `frontend/src/App.jsx` - Implemented lazy loading for panel components

## Verification Commands
```bash
cd frontend && npm run build
```

## Expected Bundle Size Improvements
Initial bundle size reduced from ~2MB to:
- Main app bundle: ~100-200KB
- Vendor chunks: separate ~500KB-1MB chunks loaded on demand
- Panel-specific chunks: loaded only when user has that role