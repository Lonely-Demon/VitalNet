# Fix Log: R3-DEVOPS-CICD-R3-005

- **Unit ID:** R3-DEVOPS-CICD-R3-005
- **Title:** Frontend CI executes dependency install scripts from lockfile packages
- **Status:** completed

## Remediation

Updated frontend CI install command to disable install lifecycle scripts:

```bash
npm ci --prefix frontend --ignore-scripts
```

This reduces supply-chain script execution risk during CI package installs.

## Files Modified

- `.github/workflows/ci.yml`
