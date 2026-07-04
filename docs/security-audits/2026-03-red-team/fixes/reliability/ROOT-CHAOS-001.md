# ROOT-CHAOS-001: No Timeout on Supabase Database Calls

## Issue Summary
Database calls could hang indefinitely without timeouts, causing:
- Resource exhaustion
- Cascading failures
- Unresponsive endpoints
- No recovery path

This was a CRITICAL (P0) reliability issue affecting all database operations.

## Fix Applied

### 1. Timeout Configuration in `backend/app/core/config.py`
Added configurable timeout settings:
- `db_timeout_default`: 10.0 seconds (fast queries)
- `db_timeout_admin`: 30.0 seconds (admin operations)
- `db_timeout_auth`: 30.0 seconds (auth operations)

### 2. Client-Level Timeout in `backend/app/core/database.py`
- Created `_TIMEOUT_DEFAULT`, `_TIMEOUT_ADMIN`, `_TIMEOUT_AUTH` httpx.Timeout objects
- Updated `supabase_anon` client to use 10s timeout (fast public queries)
- Updated `supabase_admin` client to use 30s timeout (admin operations)
- Updated `get_supabase_for_user()` to create clients with 10s timeout
- Added `_create_http_client()` helper to create httpx.Client with timeout
- Added `_create_client_with_timeout()` helper for client creation with logging

### 3. Observability in `backend/app/api/routes/admin_routes.py`
- Added logging for timeout events
- Added `_handle_db_timeout()` helper function for consistent error handling
- Added try-except blocks in `list_users()` to catch `httpx.TimeoutException`
- Returns HTTP 503 Service Unavailable with clear error message when timeout occurs

## Timeout Values Chosen and Rationale

| Client Type | Timeout | Rationale |
|-------------|---------|-----------|
| `supabase_anon` | 10s | Public read-only queries (health check, facilities list) should be fast |
| `get_supabase_for_user()` | 10s | Regular user queries with RLS should complete quickly |
| `supabase_admin` | 30s | Admin operations (list_users, create_user, etc.) may take longer |

**Why not 60s for heavy aggregations?**
- Heavy aggregations should be optimized at the query level
- 30s is sufficient for most admin operations
- Longer timeouts mask performance issues

## Files Modified

1. **`backend/app/core/config.py`**
   - Added `db_timeout_default`, `db_timeout_admin`, `db_timeout_auth` settings

2. **`backend/app/core/database.py`**
   - Added httpx import
   - Added SyncClientOptions import
   - Added timeout configuration constants
   - Added helper functions for client creation with timeout
   - Updated all three client initializations to use timeouts

3. **`backend/app/api/routes/admin_routes.py`**
   - Added logging import
   - Added httpx import
   - Added `_handle_db_timeout()` helper function
   - Added timeout error handling in `list_users()` endpoint

## Alternative Approaches Considered

1. **Query-level timeouts**: Rejected - would require modifying every query site
2. **Environment variables only**: Rejected - less maintainable than config settings
3. **Global exception handler**: Partially implemented - added route-level handling for critical endpoints

## Remaining Risks

1. **Other routes not covered**: Timeout handling is currently only added to `list_users()`. Other endpoints will return HTTP 503 automatically due to client-level timeout, but without specific error messages.

2. **Heavy aggregation queries**: The stats endpoint (`/api/admin/stats`) may need longer timeouts for large datasets. Consider adding specific timeout handling if issues arise.

3. **Connection pool exhaustion**: While timeouts prevent indefinite hangs, high traffic could still exhaust connection pools. Monitor metrics.

## Validation Steps

1. **Verify client initialization**:
   ```bash
   cd backend && python -c "from app.core.database import supabase_anon, supabase_admin; print('Clients initialized with timeouts')"
   ```

2. **Test timeout behavior**:
   - Configure a mock that delays responses beyond timeout
   - Verify HTTP 503 is returned with appropriate message

3. **Check logs**:
   - Look for "Creating Supabase client" log entries with timeout config
   - Verify timeout errors are logged with operation details

4. **Load testing**:
   - Run load tests to ensure timeouts don't cause resource exhaustion
   - Monitor for HTTP 503 responses under load

## Linked Issues

- **DATA-QUERY-R3-009**: Auth.admin.list_users() Has No Timeout (fixed as part of this combined bundle)