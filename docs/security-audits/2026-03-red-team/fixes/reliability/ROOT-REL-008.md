# ROOT-REL-008: Case delete race condition under concurrent requests

**Unit ID**: ROOT-REL-008
**Priority**: P2 (MEDIUM)
**Source IDs**: REL-008
**Status**: ✅ COMPLETED
**Fixed By**: Blue Team Remediation Agent
**Date**: 2026-04-02

---

## Finding Summary

The soft delete case endpoint in `backend/app/api/routes/security.py:50-54` had a race condition where concurrent delete requests could result in inconsistent behavior. The original code used a check-then-act pattern that could lead to silent failures or unexpected results under concurrent access.

### Severity: MEDIUM
- **Impact**: Concurrent delete requests could result in inconsistent state or silent failures
- **Affected Components**: Case deletion endpoint
- **Location**: `backend/app/api/routes/security.py:50-54`

---

## Technical Details

### Root Cause
The original code performed a non-atomic check-then-delete:
1. Check if case exists and is not deleted (lines 24-33)
2. Check authorization (lines 35-48)
3. Delete with `.is_("deleted_at", "null")` filter (lines 50-54)

The issue is that between step 1 and step 3, another request could have already deleted the case, leading to:
- Silent success (no error, but nothing was actually deleted)
- Inconsistent audit trail

### Race Condition Scenario
1. Admin A initiates delete for case X (deleted_at is null)
2. Admin B initiates delete for case X at the same time
3. Both checks pass (both see deleted_at as null)
4. Both execute UPDATE with `.is_("deleted_at", "null")` filter
5. First update succeeds, second update affects 0 rows but returns success

---

## Implemented Fix

### Optimistic Locking with Race Detection

```python
result = (
    db.table("case_records")
    .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
    .eq("id", case_id)
    .is_("deleted_at", "null")
    .execute()
)

if not result.data:
    logger.warning("Case delete race condition detected for case_id=%s", case_id)
    raise HTTPException(
        status_code=409, 
        detail="Case was already deleted or modified. Please refresh and try again."
    )

return {"status": "deleted"}
```

### Key Changes
1. **Captured UPDATE result**: Store the result of the UPDATE operation
2. **Race detection**: Check if `result.data` is empty (0 rows affected)
3. **HTTP 409 on race**: Return Conflict status with clear message
4. **Logging**: Warning log when race condition detected

---

## Why This Fix Was Chosen

The optimistic locking pattern was already implemented for ROOT-REL-007 (facility toggle). This fix uses the same pattern for consistency:
- Detects race conditions rather than preventing them
- Returns clear error to client
- Minimal code change
- Follows REST best practices (409 Conflict for concurrent modification)

---

## Files Modified

1. ✅ `backend/app/api/routes/security.py` (MODIFIED)
   - Added logging import
   - Modified soft_delete_case function (~10 lines changed)
   - Added optimistic locking with race detection

---

## Impact Assessment

### Before Fix
- ❌ Concurrent deletes could result in silent success
- ❌ No detection of race conditions
- ❌ Inconsistent audit trail

### After Fix
- ✅ Race conditions are detected and reported
- ✅ Admin receives clear feedback to refresh
- ✅ Warning logs for monitoring

---

## Status: ✅ COMPLETED

This fix addresses ROOT-REL-008 by implementing atomic case deletion with optimistic locking, detecting and reporting race conditions under concurrent delete requests.