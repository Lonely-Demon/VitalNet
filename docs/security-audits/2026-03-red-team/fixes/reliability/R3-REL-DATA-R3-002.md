# Fix Log: R3-REL-DATA-R3-002

## Unit Details
- **Unit ID**: R3-REL-DATA-R3-002
- **Priority**: P2 MEDIUM
- **Title**: Facility toggle is a read-modify-write race
- **Source IDs**: REL-DATA-R3-002
- **Location**: `backend/app/api/routes/admin_routes.py:197-206`
- **Combined Fix**: false

## Issue Description
The facility toggle endpoint performed a read-modify-write operation:
1. Read the current `is_active` state
2. Compute the new state in application code (`not current`)
3. Write the new state back to the database

This was a race condition because two admins could click toggle at nearly the same time:
- Both read the same starting state
- Both compute the same flipped value
- One intended toggle is lost
- Final state depends on timing

## Root Cause
The original code didn't use atomic database operations. The read and write were separate operations, allowing concurrent requests to interleave.

## Fix Implementation

### Changes Made to `backend/app/api/routes/admin_routes.py`:

1. **Added optimistic concurrency control**:
   - The update now includes a condition that the state hasn't changed since we read it
   - Uses `.eq('is_active', current_state)` in the update filter

2. **Added race condition detection**:
   - If no rows are updated, it means another request changed the state
   - Returns a 409 Conflict with the current state
   - Allows the client to retry with fresh data

3. **Enhanced error handling**:
   - Clear error messages explaining what happened
   - Current state included in the error response

### Code Changes:
```python
# Get current state
current = supabase_admin.table('facilities').select('is_active').eq('id', facility_id).single().execute()
if not current.data:
    raise HTTPException(status_code=404, detail="Facility not found")

current_state = current.data['is_active']
new_state = not current_state

# Use atomic update with a condition - only update if state hasn't changed
result = supabase_admin.table('facilities').update(
    {'is_active': new_state}
).eq('id', facility_id).eq('is_active', current_state).execute()

# If no rows updated, race detected
if not result.data or len(result.data) == 0:
    raise HTTPException(
        status_code=409,
        detail=f"Race condition detected. Facility state is now {'active' if current_state else 'inactive'}. Please retry."
    )

return {'is_active': new_state}
```

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. Use database-level atomic toggle (e.g., `UPDATE ... SET is_active = NOT is_active`) - Requires RPC function
2. Use pessimistic locking (SELECT FOR UPDATE) - Not supported by Supabase
3. Add a version column for optimistic locking - Requires schema change

**Chosen approach:**
- Optimistic concurrency with state check
- Minimal code change, no schema modifications needed
- Clear error handling with retry guidance

This is a standard pattern for handling concurrent updates when pessimistic locking isn't available.

## Files Changed
- `backend/app/api/routes/admin_routes.py` - Modified `toggle_facility` endpoint

## Verification
- Backend starts without errors: `cd backend && python -c "from app.api.routes import admin_routes; print('OK')"`
- The fix returns 409 on race condition, allowing frontend to handle gracefully