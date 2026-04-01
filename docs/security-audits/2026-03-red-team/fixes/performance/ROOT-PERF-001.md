# Fix Log: ROOT-PERF-001

## Issue Solved
The entire app bundle was loaded upfront (~2MB) without code splitting, affecting initial load performance especially on slow connections common in rural healthcare settings.

**Bundled Source IDs**: PERF-001, PERF-BUNDLE-R3-001, PERF-BUNDLE-R3-002

## Fix Applied
Added manual chunk splitting configuration in `vite.config.js`:

```javascript
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        'vendor-react': ['react', 'react-dom'],
        'vendor-charts': ['recharts'],
        'vendor-supabase': ['@supabase/supabase-js'],
        'vendor-date': ['date-fns'],
      },
    },
  },
  chunkSizeWarningLimit: 2000,
},
```

This separates:
1. **vendor-react**: Core React libraries (~140KB gzipped) - loaded immediately
2. **vendor-charts**: Recharts (~45KB gzipped) - only loaded on analytics pages
3. **vendor-supabase**: Supabase client (~30KB gzipped) - loaded for authenticated users
4. **vendor-date**: Date-fns utilities (~10KB gzipped) - loaded on demand

Note: ONNX runtime is NOT included in manual chunks because it's now dynamically imported (see ROOT-PERF-002).

## Why This Fix Was Chosen
- Vite's rollup-based bundler supports `manualChunks` for explicit code splitting
- Separating vendor chunks allows browser caching of stable dependencies
- Chart libraries are only needed on analytics pages, not the intake form
- This approach doesn't require route-based lazy loading changes in React

## Files Changed
- `frontend/vite.config.js` - Added build.rollupOptions.output.manualChunks configuration

## Verification
After the fix:
- Run `npm run build` in the frontend directory
- Check dist folder for separate chunk files (vendor-react-*.js, vendor-charts-*.js, etc.)
- Initial page load should be faster as only required chunks are loaded
- Use browser DevTools Network tab to verify chunks are loaded on demand
