# Fix Log: UNRESOLVED-DEVOPS-ENV-R3-007

- **Unit ID:** UNRESOLVED-DEVOPS-ENV-R3-007
- **Title:** CI Frontend Build Is Staging-Pinned at Compile Time
- **Status:** completed

## Remediation

Removed hardcoded staging URL from CI and switched to environment-scoped variable:

```yaml
VITE_API_BASE_URL: ${{ vars.VITE_API_BASE_URL }}
```

This prevents forced staging pinning in build artifacts.

## Files Modified

- `.github/workflows/ci.yml`
