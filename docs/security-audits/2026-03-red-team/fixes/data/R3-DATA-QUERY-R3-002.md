# Fix Log: R3-DATA-QUERY-R3-002

## Unit Details
- **Unit ID**: R3-DATA-QUERY-R3-002
- **Priority**: P0 CRITICAL
- **Title**: SELECT * on case_records Table Without Column Projection
- **Source IDs**: DATA-QUERY-R3-002
- **Location**: `backend/app/api/routes/analytics_routes.py:27`

## Issue Description
Analytics queries were using `SELECT *` which:
- Exposes unnecessary PHI columns
- Increases network bandwidth usage
- Violates data minimization principles
- Could leak sensitive fields to unauthorized code paths

## Root Cause
The `base_query()` function used `.select("*")` without explicit column projection.

## Fix Implementation
Replaced all `SELECT *` with explicit column projection:
1. Each query now specifies only the columns it needs
2. Analytics queries only fetch aggregate-relevant columns (id, triage_level, created_at, etc.)
3. PHI columns (patient_name, vitals, etc.) excluded from analytics queries

### Code Changes
**File**: `backend/app/api/routes/analytics_routes.py`

```python
# Before
def base_query():
    q = db.table("case_records").select("*", count="exact")...

# After - explicit column projection per query
async def query_total():
    q = db.table("case_records").select("id", count="exact")...

async def query_triage_dist():
    q = db.table("case_records").select("triage_level")...

async def query_week_cases():
    q = db.table("case_records").select("created_at")...
```

## Validation
- Code compiles successfully
- Each query fetches only required columns
- Data minimization principle enforced

## Status
**COMPLETED** - 2026-03-31
