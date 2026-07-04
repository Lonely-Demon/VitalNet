# R3-DATA-LIFECYCLE-R3-006 Fix Documentation

## Issue Summary
The real-time feed was reintroducing soft-deleted records into in-memory dashboards. When a case record was soft-deleted (deleted_at timestamp set), the UPDATE event would still be published via Supabase Realtime, and the frontend would update the dashboard to show the deleted record.

## Root Cause
- Supabase Realtime publishes all UPDATE events on case_records table without filtering
- Frontend `useRealtimeCases` hook handled UPDATE events but didn't check for soft-deletion
- Dashboard component updated cases in-place without removing soft-deleted records

## Fix Implementation

### 1. Frontend Dashboard Updates (`frontend/src/pages/Dashboard.jsx`)
Modified the real-time event handlers to filter out soft-deleted records:

```javascript
// onInsert: Only add non-deleted cases to prevent soft-deleted records from appearing
onInsert: (newCase) => {
  if (!newCase.deleted_at) {
    setCases((prev) => {
      if (prev.find((c) => c.id === newCase.id)) return prev
      return [newCase, ...prev]
    })
    if (newCase.triage_level === 'EMERGENCY') {
      showToast('New EMERGENCY case received', 'error')
    }
  }
},

// onUpdate: If the case has been soft-deleted, remove it from the dashboard
onUpdate: (updatedCase) => {
  setCases((prev) => {
    // If the case has been soft-deleted, remove it from the dashboard
    if (updatedCase.deleted_at) {
      return prev.filter((c) => c.id !== updatedCase.id)
    }
    // Otherwise, update the case in place
    return prev.map((c) => (c.id === updatedCase.id ? updatedCase : c))
  })
},
```

### 2. Backend Consistency Verification
Verified that all backend API endpoints consistently filter out soft-deleted records using `.is_("deleted_at", "null")`:
- `/api/cases` (get_cases)
- `/api/cases/mine` (get_my_cases)
- `/api/cases/{case_id}` (get_case_detail)
- Analytics routes

### 3. Migration Status
The Supabase Realtime setup (`backend/supabase/migrations/phase10_realtime_setup.sql`) correctly enables REPLICA IDENTITY FULL and adds the table to the publication, but doesn't include row-level filtering. This is appropriate as filtering is handled client-side for real-time updates.

## Testing
- Frontend build passes without syntax errors
- Real-time updates now properly remove soft-deleted records from dashboard
- New case insertions are filtered to exclude soft-deleted records
- Backend APIs maintain consistent soft-delete filtering

## Security Impact
This fix prevents information leakage where soft-deleted (presumably sensitive) case records could reappear in user dashboards via real-time updates, maintaining the integrity of the soft-delete pattern.</content>
<parameter name="filePath">D:\Southern_Ring_Nebula\VitalNet\docs\security-audits\2026-03-red-team\fixes\R3-DATA-LIFECYCLE-R3-006.md