# R3-DATA-LIFECYCLE-R3-006: Soft-Delete Filtering Consistency

## Problem
Soft-delete filtering (`deleted_at IS NULL`) is inconsistently applied:
- Missing in some realtime subscription filters
- Missing in some dashboard queries
- Inconsistent between frontend and backend
- Potential for "ghost" records appearing in UI

This creates:
- Confusion when deleted cases reappear
- Inconsistent reporting
- Audit trail gaps
- Potential PHI exposure

## Root Cause
1. Frontend realtime subscriptions don't filter `deleted_at`
2. Some backend queries omit soft-delete filtering
3. No centralized enforcement of soft-delete logic
4. Inconsistent patterns across codebase

## Solution
Implement consistent soft-delete filtering:
1. **Frontend**: Add `deleted_at IS NULL` to all realtime subscriptions
2. **Frontend**: Add soft-delete filtering to dashboard queries
3. **Backend**: Ensure all queries include soft-delete filtering
4. **Backend**: Add helper function for consistent filtering

## Files Modified
- `frontend/src/hooks/useRealtimeCases.js`
- `frontend/src/pages/Dashboard.jsx`
- `backend/app/api/routes/cases.py`

## Evidence
- Realtime subscriptions and dashboard filtering now exclude soft-deleted cases consistently.

## Changes Made
### Frontend Realtime
```javascript
// Added deleted_at filter to all subscription filters
const channel = supabase
  .channel(channelName)
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'case_records',
      filter: `deleted_at=is.null${facilityId ? `,facility_id=eq.${facilityId}` : ''}${userId ? `,submitted_by=eq.${userId}` : ''}`,
    },
    (payload) => {
      // ...
    }
  )
```

### Frontend Dashboard
```javascript
// Added consistent deleted_at filtering
const visibleCases = filter === 'pending'
  ? cases.filter(c => !c.reviewed_at && !c.deleted_at)
  : cases.filter(c => !c.deleted_at);
```

### Backend Helper
```python
def apply_soft_delete(query):
    """Apply consistent soft-delete filtering to queries."""
    return query.is_("deleted_at", "null")
```

## Validation
- Deleted cases no longer appear in realtime updates
- Dashboard shows consistent case counts
- Audit logs confirm deleted cases are filtered
- Tested with various deletion scenarios

## Compliance
- **HIPAA §164.316(b)(2)(i)**: Record retention and availability
- **GDPR Article 17**: Right to erasure ("right to be forgotten")
- **IEC 62304**: Data lifecycle management
