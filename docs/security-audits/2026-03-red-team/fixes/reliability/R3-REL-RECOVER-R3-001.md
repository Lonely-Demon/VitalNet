# Fix Log: R3-REL-RECOVER-R3-001

## Issue Summary
- **Unit ID**: R3-REL-RECOVER-R3-001
- **Title**: Startup hard-fails if the ML model cannot load
- **Severity**: CRITICAL (P0)
- **Location**: `backend/app/main.py:36-39`

## Problem Description
The backend hard-fails on startup if ML model files cannot be loaded, causing complete service outage. This is a reliability issue because the service should gracefully degrade or provide a clear recovery path rather than refusing to start.

### Original Code (Before Fix)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the ML classifier once at startup; release on shutdown."""
    load_classifier()
    logger.info("VitalNet API started")
```

If `load_classifier()` raises an exception (e.g., missing model file, corrupt model, missing dependencies), the API would never finish booting. The health check and all fallback paths were unreachable, so the service had no degraded mode.

## Fix Applied

### 1. Graceful Degradation in main.py (lines 36-58)
The ML model loading is now wrapped in a try/except block that:
- Catches any exceptions during ML loading
- Sets `app.state.ml_available` flag to indicate ML availability
- Logs clear warnings/errors for operators
- Allows the service to start in degraded mode

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the ML classifier once at startup; release on shutdown."""
    # Wrap ML loading in try/except to allow graceful degradation
    try:
        ml_loaded = load_classifier()
        app.state.ml_available = ml_loaded
        if not ml_loaded:
            logger.warning(
                "ML classifier failed to load — starting in degraded mode. "
                "Case submission will use LLM-only fallback triage."
            )
    except Exception as e:
        # Log the error but allow app to start
        logger.error(
            "ML classifier loading raised exception: %s. Starting in degraded mode. "
            "Case submission will use LLM-only fallback triage.",
            e,
        )
        app.state.ml_available = False

    logger.info("VitalNet API started (ML available: %s)", app.state.ml_available)
    yield
    logger.info("VitalNet API shutting down")
```

### 2. Fallback Triage in classifier.py
The `predict_triage()` function now checks `is_ml_available()` and falls back to rule-based triage if ML is unavailable:

```python
def predict_triage(form_data: Dict[str, Any]) -> Dict[str, Any]:
    if not is_ml_available():
        logger.warning("ML classifier unavailable — using fallback triage")
        return get_fallback_triage(form_data)
    return _predict_enhanced(form_data)
```

### 3. Health Check Returns 503 When Degraded
The health endpoint (`/api/health`) now returns HTTP 503 when the service is in degraded mode:

```python
is_healthy = db_status == "connected" and classifier_loaded
# Return 503 Service Unavailable when degraded
if not is_healthy:
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=response_body)
```

## Rationale for Approach

1. **Minimal Changes**: The fix is targeted and doesn't change any existing functionality when the ML model is available.

2. **Clear Observability**: Operators are informed via logs when the service starts in degraded mode, and the health endpoint clearly indicates the degraded state.

3. **Fallback Functionality**: The rule-based fallback triage provides basic triage capability even without the ML model, ensuring the service remains functional.

4. **No Breaking Changes**: The fix is backward compatible - existing deployments with working ML models continue to work exactly as before.

## Files Changed

1. **backend/app/main.py** (lines 36-58)
   - Added try/except around ML model loading in lifespan
   - Added `app.state.ml_available` flag
   - Updated health endpoint to return 503 when degraded

2. **backend/app/ml/classifier.py**
   - `predict_triage()` now checks `is_ml_available()` and falls back to rule-based triage
   - Added `get_fallback_triage()` function for rule-based triage

3. **backend/test_graceful_degradation.py** (test file)
   - Fixed test assertions to use correct case (EMERGENCY, URGENT, ROUTINE)
   - Fixed Unicode encoding issues for Windows compatibility

## Verification

Run the test to verify the fix:
```bash
cd backend && python test_graceful_degradation.py
```

Expected output:
- Classifier load fails gracefully (returns False, no exception raised)
- Fallback prediction system works correctly for emergency, urgent, and routine cases
- Classifier info retrieval works even when model isn't loaded

## Remaining Risks

1. **Reduced Accuracy**: The fallback rule-based triage is less accurate than the ML model. This is acceptable as a degraded mode but operators should be notified to restore the ML model.

2. **Monitoring Required**: Operators should monitor the health endpoint to detect when the service is in degraded mode.

3. **Model Recovery**: When the ML model is restored, the service needs to be restarted to reload the model (this is by design to ensure consistency).

## Suggested Validation Steps

1. Start the backend without the ML model file - verify it starts in degraded mode
2. Check the health endpoint returns 503 when in degraded mode
3. Submit a case - verify it uses the fallback triage
4. Restore the ML model and restart - verify it returns to normal mode
5. Check logs for degradation warnings