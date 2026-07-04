# Fix Log: R3-REL-DATA-R3-003

## Unit Details
- **Unit ID**: R3-REL-DATA-R3-003
- **Priority**: P2 MEDIUM
- **Title**: Case pagination is not stable across equal timestamps
- **Source IDs**: REL-DATA-R3-003
- **Location**: `backend/app/api/routes/cases.py:149-179,224-247`
- **Combined Fix**: false

## Issue Description
The case pagination endpoints sorted only by `triage_priority` and `created_at` without a unique tie-breaker. When two cases shared the same timestamp and sort key:
1. Page 1 could return one row and page 2 could neither uniquely resume nor distinguish the tie
2. The dashboard could skip or duplicate records during pagination
3. Users might see inconsistent results when navigating through pages

## Root Cause
The keyset pagination used only two columns (`triage_priority` and `created_at`) as the cursor. When multiple cases had identical values for both columns, there was no way to determine the exact position in the sorted order.

## Fix Implementation

### Changes Made to `backend/app/api/routes/cases.py`:

1. **Added `id` as a unique tie-breaker**:
   - Added `id` to the ORDER BY clause in both pagination endpoints
   - This ensures stable, deterministic pagination even when timestamps are equal

2. **Updated cursor parameters**:
   - Added `before_id` parameter to both endpoints
   - The cursor now includes the unique `id` for precise positioning

3. **Updated response to include nextId**:
   - Added `nextId` to the pagination response
   - Frontend can now pass this as `before_id` for the next page

4. **Updated the filter logic**:
   - Modified the cursor filter to use three-column keyset pagination
   - Handles cases where `created_at` is equal but `id` differs

### Code Changes:

**get_cases endpoint:**
```python
# Added id to order by
.order("triage_priority", desc=False)
.order("created_at", desc=True)
.order("id", desc=True)  # Unique tie-breaker

# Updated cursor filter
if before_id is not None:
    query = query.or_(
        f"triage_priority.gt.{before_priority},"
        f"and(triage_priority.eq.{before_priority},created_at.lt.{before_time}),"
        f"and(triage_priority.eq.{before_priority},created_at.eq.{before_time},id.lt.{before_id})"
    )

# Added nextId to response
"nextId": cases[-1]["id"] if has_more and cases else None,
```

**get_my_cases endpoint:**
```python
# Added id to order by
.order("created_at", desc=True)
.order("id", desc=True)  # Unique tie-breaker

# Updated cursor filter
if before and before_id:
    query = query.or_(
        f"created_at.lt.{before},"
        f"and(created_at.eq.{before},id.lt.{before_id})"
    )

# Added nextId to response
"nextId": rows[limit - 1]["id"] if has_more and rows else None,
```

## Why This Fix Was Chosen

**Alternative approaches considered:**
1. Use OFFSET-based pagination - Less efficient, doesn't solve the stability issue
2. Add a separate sequence column - Requires database schema change
3. Use UUID-based sorting - Would require changing the primary key

**Chosen approach:**
- Use the existing `id` column as a unique tie-breaker
- Minimal code change, no schema modifications needed
- Standard keyset pagination pattern with composite key

This is a standard pattern for stable pagination: always include a unique column (id) as the final sort key to ensure total ordering.

## Files Changed
- `backend/app/api/routes/cases.py` - Modified `get_cases` and `get_my_cases` endpoints

## Verification
- Backend starts without errors: `cd backend && python -c "from app.api.routes import cases; print('OK')"`
- The fix is backward compatible - existing pagination will continue to work
- Frontend should be updated to pass `before_id` when available for more stable pagination