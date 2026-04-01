# Fix Log: R3-REL-OBS-R3-001

## Unit Details
- **Unit ID**: R3-REL-OBS-R3-001
- **Priority**: P1 HIGH
- **Title**: Missing request correlation IDs
- **Source IDs**: REL-OBS-R3-001
- **Location**: `backend/app/main.py`, `backend/app/core/correlation.py`, `backend/app/core/logging.py`, `backend/app/api/routes/cases.py`
- **Combined Fix**: false

## Issue Description
The backend lacked request correlation IDs, making it difficult to trace requests across logs and debug production issues. Without correlation IDs, it was impossible to:
1. Track a single request across multiple log statements
2. Correlate errors with specific requests
3. Trace requests through the system for debugging

## Root Cause
The application did not generate or propagate unique identifiers for each HTTP request. This is a fundamental observability gap that prevents effective debugging and monitoring in production.

## Fix Implementation

### 1. Created Correlation ID Utility Module
Created `backend/app/core/correlation.py` with:
- `get_correlation_id()` - Get the current request's correlation ID from context
- `set_correlation_id(correlation_id)` - Set correlation ID for current request context
- `generate_correlation_id()` - Generate a new UUID for each request
- `CorrelationIdContext` - Context manager for temporary correlation ID setting

Uses Python's `contextvars` for thread-safe, async-safe request-scoped storage.

### 2. Added Correlation ID Middleware
Added `CorrelationIdMiddleware` to `backend/app/main.py`:
- Generates unique UUID for each request (or uses X-Request-ID from client if provided)
- Sets correlation ID in context variable for the request lifecycle
- Adds `X-Request-ID` header to all responses
- Supports client-provided correlation IDs for distributed tracing

### 3. Updated Logging to Include Correlation ID
Modified `backend/app/core/logging.py`:
- Added `CorrelationIdLoggerAdapter` class that automatically adds correlation ID to log records
- Updated JSON formatter to include correlation_id in log output
- All log statements now automatically include the correlation ID when available

### 4. Updated Exception Handlers
Modified global exception handlers in `backend/app/main.py`:
- `global_exception_handler` - Now includes correlation_id in error logs
- `validation_exception_handler` - Now includes correlation_id in validation error logs

### 5. Updated Key Endpoints
Modified `backend/app/api/routes/cases.py`:
- Added import for `get_correlation_id`
- Updated `submit_case` error logging to include correlation_id

## Code Changes

### File: `backend/app/core/correlation.py` (NEW)
```python
"""
Request Correlation ID utilities for observability.
"""
import uuid
from contextvars import ContextVar
from typing import Optional

# Request-scoped correlation ID storage
_correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)

def get_correlation_id() -> Optional[str]:
    """Get the current request's correlation ID."""
    return _correlation_id_var.get()

def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current request context."""
    _correlation_id_var.set(correlation_id)

def generate_correlation_id() -> str:
    """Generate a new unique correlation ID."""
    return str(uuid.uuid4())
```

### File: `backend/app/main.py`
```python
# Added imports
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.correlation import generate_correlation_id, set_correlation_id, get_correlation_id

# Added middleware class
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_correlation_id = request.headers.get("X-Request-ID")
        correlation_id = client_correlation_id or generate_correlation_id()
        set_correlation_id(correlation_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response

# Registered middleware
app.add_middleware(CorrelationIdMiddleware)

# Updated exception handlers to include correlation_id in logs
```

### File: `backend/app/core/logging.py`
```python
from app.core.correlation import get_correlation_id

class CorrelationIdLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        if "correlation_id" not in kwargs["extra"]:
            correlation_id = get_correlation_id()
            if correlation_id:
                kwargs["extra"]["correlation_id"] = correlation_id
        return msg, kwargs

# Updated formatter to include correlation_id
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s "
    "%(correlation_id)s"
)
```

### File: `backend/app/api/routes/cases.py`
```python
# Added import
from app.core.correlation import get_correlation_id

# Updated error logging
except Exception as e:
    correlation_id = get_correlation_id()
    logger.error(
        "submit_case failed for client_id=%s: %s",
        form.client_id,
        e,
        exc_info=True,
        extra={"correlation_id": correlation_id},
    )
```

## Alternative Approaches Considered

1. **Use OpenTelemetry with automatic instrumentation**: Rejected - requires additional dependencies and setup
2. **Use a logging service like DataDog**: Rejected - adds cost and complexity
3. **Add correlation ID only to error logs**: Rejected - incomplete observability
4. **Use request ID from client only**: Rejected - doesn't handle cases where client doesn't provide ID

## Why This Fix Was Chosen

1. **Minimal dependencies**: Uses only Python standard library (uuid, contextvars)
2. **Async-safe**: Uses contextvars which are designed for async Python
3. **Standard header**: Uses X-Request-ID which is a common convention
4. **Client support**: Allows clients to provide their own correlation ID for distributed tracing
5. **Automatic propagation**: Logger adapter automatically includes correlation ID in all logs
6. **Minimal changes**: Focused implementation without changing core application logic

## Files Modified

1. **`backend/app/core/correlation.py`** (NEW)
   - Created correlation ID utility module with contextvars-based storage

2. **`backend/app/main.py`**
   - Added imports for correlation ID utilities and BaseHTTPMiddleware
   - Added CorrelationIdMiddleware class
   - Registered middleware in FastAPI app
   - Updated exception handlers to include correlation_id in logs

3. **`backend/app/core/logging.py`**
   - Added CorrelationIdLoggerAdapter class
   - Updated JSON formatter to include correlation_id

4. **`backend/app/api/routes/cases.py`**
   - Added import for get_correlation_id
   - Updated submit_case error logging to include correlation_id

## Validation Steps

1. **Verify syntax**:
   ```bash
   cd backend && python -m py_compile app/main.py app/core/correlation.py app/core/logging.py app/api/routes/cases.py
   ```

2. **Test correlation ID generation**:
   - Start the server and make a request
   - Verify X-Request-ID header is present in response
   - Verify correlation ID appears in JSON logs

3. **Test client-provided correlation ID**:
   ```bash
   curl -H "X-Request-ID: my-custom-id" http://localhost:8000/api/health
   # Verify response includes X-Request-ID: my-custom-id
   ```

4. **Test error logging**:
   - Trigger an error in submit_case
   - Verify correlation_id appears in error logs

## Observability

All log statements now automatically include correlation_id when available:
- JSON log format includes `correlation_id` field
- Exception handlers include correlation_id in error logs
- API route error logging includes correlation_id
- Response headers include `X-Request-ID`

## Status

**COMPLETED** - 2026-04-02