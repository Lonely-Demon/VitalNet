# Fix Log: R3-DEVOPS-CICD-R3-006

- **Unit ID:** R3-DEVOPS-CICD-R3-006
- **Title:** Checkout leaves repository token material available to later steps by default
- **Status:** completed

## Remediation

Hardened all checkout steps:

```yaml
with:
  persist-credentials: false
  fetch-depth: 1
```

This prevents token persistence in git config for later workflow steps.

## Files Modified

- `.github/workflows/ci.yml`
