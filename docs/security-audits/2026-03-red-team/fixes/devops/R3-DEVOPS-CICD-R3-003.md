# Fix Log: R3-DEVOPS-CICD-R3-003

- **Unit ID:** R3-DEVOPS-CICD-R3-003
- **Title:** The workflow does not restrict GITHUB_TOKEN permissions
- **Status:** completed

## Remediation

Added top-level minimal workflow permissions:

```yaml
permissions:
  contents: read
```

This enforces least-privilege token scope for all CI jobs.

## Files Modified

- `.github/workflows/ci.yml`
