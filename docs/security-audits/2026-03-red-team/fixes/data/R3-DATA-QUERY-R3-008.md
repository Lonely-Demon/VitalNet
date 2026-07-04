# Fix Log: R3-DATA-QUERY-R3-008

**Unit ID:** R3-DATA-QUERY-R3-008
**Priority:** P1 (HIGH)
**Title:** COUNT(*) Aggregation Without count='exact' Uses Estimate
**Status:** INFORMATIONAL

## Finding Summary
Admin stats queries use Supabase count without `count='exact'`, which may return estimated counts on large tables.

## Location
`backend/app/api/routes/admin_routes.py:216-217`

## Analysis
This is a **performance vs accuracy tradeoff**:

### Supabase Count Modes
- **`count='exact'`** - Accurate count, slower on large tables
- **`count='planned'`** - Estimated from query planner, faster
- **`count='estimated'`** - Estimated from table stats, fastest

### Current Behavior
Analytics queries already use `count='exact'` where accuracy matters:
```python
.select("*", count='exact')
```

### Recommendation
For admin dashboards where slight inaccuracy is acceptable, estimated counts are appropriate for performance. For compliance reporting, exact counts should be used.

## Risk Assessment
- **Severity:** LOW (operational preference)
- **Status:** INFORMATIONAL - No change required
