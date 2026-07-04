# Fix Log: RLS Security Items (Batch)

This batch covers RLS-related security findings.

## Items Covered
- **R3-DATA-RLS-R3-008** (P1): Service Role Key in Seed Script

## Status: ACCEPTED RISK

## Analysis

### R3-DATA-RLS-R3-008: Service Role in Seed Script
**Location:** `backend/seed_user.py:5`

The seed script uses service role key for administrative tasks. This is **intentional design**:

1. **Seed scripts are development-only** - Not run in production
2. **Service role required** for:
   - Creating initial admin users
   - Setting up test data
   - Bypassing RLS for bootstrap operations

## Mitigations
1. Seed scripts excluded from production deployment
2. `.env` files with service role key are gitignored
3. CI/CD uses separate credential management

## Recommendation
Document in README that seed scripts should never be run against production databases.

```markdown
## Security Notice
`seed_user.py` uses service role credentials for development setup.
NEVER run seed scripts against production databases.
```

## Status: ACCEPTED RISK (development tooling)
