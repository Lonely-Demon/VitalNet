# Fix Log: R3-DATA-RLS-R3-004

**Unit ID:** R3-DATA-RLS-R3-004
**Priority:** P0 (CRITICAL)
**Title:** Realtime Subscription Filter Can Be Overwritten by Client
**Status:** MITIGATED (server-side RLS enforced)

## Finding Summary
Frontend realtime subscription filter is set client-side, which could theoretically be overwritten by malicious client code to subscribe to other facilities' data.

## Location
`frontend/src/hooks/useRealtimeCases.js:23-44`

## Analysis
While the client-side filter can be modified, **Supabase Realtime respects RLS policies**:

1. **Server-side enforcement** - Even if client modifies filter, RLS policies on `case_records` table prevent data access
2. **Auth context required** - Realtime subscriptions carry JWT, enabling RLS evaluation

## Mitigations Applied
1. **RLS policies on case_records** ensure users only see their facility's data regardless of subscription filter
2. **Phase15 migration** adds comprehensive RLS for SELECT operations

## Verification
From Supabase documentation:
> "Realtime respects Row Level Security policies. Users will only receive changes for rows they have access to."

## Additional Hardening (Recommended)
Consider adding explicit facility_id check in realtime subscription setup:
```javascript
.on('postgres_changes', {
  event: '*',
  schema: 'public',
  table: 'case_records',
  filter: `facility_id=eq.${user.facility_id}`  // Defense in depth
}, callback)
```

## Files Modified
- `backend/supabase/migrations/phase15_data_security_hardening.sql` (RLS policies)

## Risk Assessment
- **Before:** MEDIUM - Client could attempt filter manipulation
- **After:** LOW - Server-side RLS prevents unauthorized access regardless
