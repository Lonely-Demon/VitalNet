# Fix Log: R3-DEVOPS-MONITOR-R3-001

## Unit Information
- **Unit ID:** R3-DEVOPS-MONITOR-R3-001
- **Title:** Degraded health checks still return HTTP 200
- **Priority:** P0 CRITICAL
- **Source IDs:** DEVOPS-MONITOR-R3-001

## Problem Description

The health check endpoint at `/api/health` was returning HTTP 200 OK even when the system was in a degraded state (database disconnected or classifier not loaded). This caused issues for load balancers and orchestrators that rely on HTTP status codes to determine instance health, as they would incorrectly route traffic to unhealthy instances.

### Original Behavior
- System degraded (DB down or classifier not loaded) → HTTP 200 with `{"status": "degraded"}`
- Load balancers interpret HTTP 200 as healthy
- Traffic continues to route to unhealthy instances

## Fix Applied

Modified `backend/app/main.py` to return HTTP 503 Service Unavailable when the system is degraded:

1. **Added import:** Imported `status` from `fastapi` to access HTTP status code constants
2. **Refactored health logic:** Extracted health determination into `is_healthy` boolean variable
3. **Conditional response:** Return `JSONResponse` with status code 503 when degraded, otherwise return normal response

### Code Changes

**File:** `backend/app/main.py`

**Before:**
```python
from fastapi import FastAPI, Request

@app.get("/api/health")
async def health():
    # ... health checks ...
    return {
        "status": "ok" if db_status == "connected" and classifier_loaded else "degraded",
        "database": db_status,
        "classifier": classifier_status,
        "version": "0.2.0",
    }
```

**After:**
```python
from fastapi import FastAPI, Request, status

@app.get("/api/health")
async def health():
    # ... health checks ...
    is_healthy = db_status == "connected" and classifier_loaded
    response_body = {
        "status": "ok" if is_healthy else "degraded",
        "database": db_status,
        "classifier": classifier_status,
        "version": "0.2.0",
    }

    # Return 503 Service Unavailable when degraded
    if not is_healthy:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=response_body)
    return response_body
```

## Why This Fix Was Chosen

1. **Standards-compliant:** HTTP 503 Service Unavailable is the standard response for temporary server unavailability (RFC 7231)
2. **Load balancer compatible:** All major load balancers (AWS ALB, Nginx, HAProxy, Kubernetes) recognize 503 as unhealthy
3. **Minimal change:** Only modifies the response status code, preserving the JSON body for debugging
4. **No breaking changes:** The JSON response structure remains identical; only the HTTP status code changes
5. **Alternative considered:** Using `raise HTTPException(status_code=503)` was rejected because it would trigger exception handlers and potentially obscure the health status details in logs

## Files Changed

1. `backend/app/main.py` - Modified health endpoint to return 503 when degraded
2. `backend/tests/test_health_endpoint.py` - Added test coverage for health endpoint status codes (new file)

## Verification

### Test Commands
```bash
# Run health endpoint tests
cd backend && python tests/test_health_endpoint.py

# Expected output:
# ======================================================================
# VitalNet Health Endpoint Test
# Testing fix for R3-DEVOPS-MONITOR-R3-001
# ======================================================================
# [PASS] Health endpoint returns correct JSON structure
# [PASS] Healthy system returns HTTP 200
# [PASS] All degradation scenarios handled correctly
# ======================================================================
# ✓ ALL TESTS PASSED
# ======================================================================
```

### Manual Verification
```bash
# Test healthy state (should return 200)
curl -i http://localhost:8000/api/health

# Test degraded state (simulate by stopping database or unloading classifier)
# Should return 503 with same JSON body
```

## Status

**Status:** COMPLETED

The fix has been implemented and tested. The health endpoint now correctly returns:
- **HTTP 200 OK** when `status == "ok"` (database connected AND classifier loaded)
- **HTTP 503 Service Unavailable** when `status == "degraded"` (database error OR classifier not loaded)

## Related Issues

- R3-DEVOPS-MONITOR-R3-002: Health coverage misses the clinician write path and RLS-scoped auth path
- R3-DEVOPS-INFRA-R3-001: Public Health Check Becomes an Anonymous Internal-State Oracle
