# ROOT-REL-007: Facility toggle is non-atomic under concurrent admins

**Unit ID**: ROOT-REL-007
**Priority**: P2 (MEDIUM)
**Source IDs**: REL-007, QA-EDGE-R3-003
**Status**: ✅ COMPLETED
**Fixed By**: Blue Team Remediation Agent
**Date**: 2026-04-02

---

## Finding Summary

The facility toggle endpoint in `backend/app/api/routes/admin_routes.py:203` had a race condition where two concurrent admin toggle requests could result in one intended flip being lost. This is a classic read-modify-write race condition.

### Severity: MEDIUM
- **Impact**: Under concurrent admin operations, facility state can become inconsistent
- **Affected Components**: Admin facility management
- **Location**: `backend/app/api/routes/admin_routes.py:203`
- **Linked R3**: QA-EDGE-R3-003 ("Facility toggle is non-atomic under concurrent admins")

---

## Technical Details

### Root Cause
The original code performed a non-atomic read-modify-write:
1. Read current state: `current = ...select('is_active')...`
2. Compute new state: `new_state = not current.data['is_active']`
3. Write new state: `update({'is_active': new_state})`

If two admins clicked toggle at nearly the same time:
- Both read the same state (e.g., `is_active=true`)
- Both compute the same new state (`is_active=false`)
- Both write the same state
- One intended flip is lost

---

## Implemented Fix

### Atomic Toggle with Optimistic Locking
The fix uses optimistic locking with a conditional UPDATE:

```python
# Step 1: Read current state
current = supabase_admin.table('facilities').select('id, is_active').eq('id', facility_id).single().execute()

# Step 2: Compute new state
current_state = current.data['is_active']
new_state = not current_state

# Step 3: Conditional UPDATE - only succeeds if state hasn't changed
result = (
    supabase_admin.table('facilities')
    .update({'is_active': new_state})
    .eq('id', facility_id)
    .eq('is_active', current_state)  # Optimistic lock: only update if still current
    .execute()
)

# Step 4: Handle race condition detected
if not result.data:
    logger.warning("Facility toggle race condition detected for facility_id=%s", facility_id)
    raise HTTPException(status_code=409, detail="Facility was modified by another admin. Please retry.")
```

### Key Features
1. **Optimistic Locking**: The UPDATE includes a WHERE clause `eq('is_active', current_state)` that ensures the update only succeeds if no other admin has modified the facility
2. **Race Detection**: If the UPDATE affects 0 rows, a race condition was detected
3. **Graceful Degradation**: Returns HTTP 409 Conflict with a clear message telling the admin to retry
4. **Logging**: Warning log when race condition is detected for debugging/auditing

---

## Why This Fix Was Chosen

### Alternatives Considered
1. **Database-level toggle**: Use SQL `UPDATE ... SET is_active = NOT is_active` - Rejected: Supabase client doesn't support raw SQL easily
2. **Pessimistic locking**: Use `SELECT ... FOR UPDATE` - Rejected: Requires transaction support not easily available via Supabase client
3. **Optimistic locking with retry**: ✅ **CHOSEN** - Simple, effective, works with Supabase client

### Rationale
- The optimistic locking approach is the standard pattern for handling concurrent modifications
- It detects race conditions rather than preventing them, which is appropriate for this use case
- The HTTP 409 response tells the client to retry, which will succeed once the other admin's change is complete
- Minimal code change with clear semantics

---

## Testing Performed

### 1. Syntax Verification
```bash
cd backend && python -m py_compile app/api/routes/admin_routes.py
# ✅ No syntax errors
```

### 2. Code Review
- ✅ Optimistic lock uses `eq('is_active', current_state)` in UPDATE WHERE clause
- ✅ Race condition detected when UPDATE affects 0 rows
- ✅ HTTP 409 returned with user-friendly message
- ✅ Warning log emitted for observability

### 3. Exception Handling
- 404 if facility not found (existing behavior preserved)
- 409 if concurrent modification detected (new behavior)
- Other errors propagate to caller (existing behavior preserved)

---

## Files Modified

1. ✅ `backend/app/api/routes/admin_routes.py` (MODIFIED)
   - Added import for HTTPException (already present)
   - Modified `toggle_facility` function (~20 lines changed)
   - Added optimistic locking with race detection
   - Added warning log for race condition events

---

## Impact Assessment

### Before Fix
- ❌ Two concurrent toggles could result in one flip being lost
- ❌ No detection of race conditions
- ❌ Silent data inconsistency

### After Fix
- ✅ Race conditions are detected and reported
- ✅ Admin receives clear feedback to retry
- ✅ Warning logs for monitoring race condition frequency
- ✅ Consistent state maintained under concurrent access

### User Experience
- **Admins**: May see "retry" message if they click toggle at the same time as another admin - simple refresh and retry resolves

---

## Compliance & Standards

- ✅ Follows REST API best practices (409 Conflict for concurrent modification)
- ✅ Proper logging for observability
- ✅ Clear error messages for clients
- ✅ No breaking changes to existing API contract (adds new error code only on conflict)

---

## Deployment Notes

1. **No Breaking Changes**: Only adds new 409 error response on race condition
2. **No Environment Variables**: No new configuration required
3. **No Database Changes**: Uses existing schema
4. **Backward Compatible**: Existing behavior preserved for non-conflicting updates

---

## Status: ✅ COMPLETED

This fix addresses ROOT-REL-007 by implementing atomic facility toggle with optimistic locking, detecting and reporting race conditions under concurrent admin access.

**Next steps**:
1. Deploy to staging environment
2. Monitor logs for race condition warnings
3. Consider adding retry logic in frontend (automatic retry on 409)