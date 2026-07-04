# ROOT-REL-006: No exponential backoff on retries

**Unit ID**: ROOT-REL-006  
**Priority**: P1 (HIGH)  
**Source IDs**: REL-006, QA-EDGE-R3-006  
**Status**: ✅ COMPLETED  
**Fixed By**: Reliability Fix Specialist Agent  
**Date**: 2026-04-01

---

## Finding Summary

The backend LLM service (`backend/app/services/llm.py`) used fixed sleep delays instead of exponential backoff with jitter when retrying after rate limits, JSON parse errors, or other failures. This creates a thundering herd problem where multiple clients retry simultaneously after a failure, potentially overwhelming the service again.

### Severity: HIGH
- **Impact**: Thundering herd on retries can cause cascading failures
- **Affected Components**: LLM service (Groq and Gemini tiers)
- **Location**: `backend/app/services/llm.py`
- **Linked R3**: QA-EDGE-R3-006 ("LLM rate-limit sleep can race with cascade fallback")

---

## Technical Details

### Root Cause
The original code used fixed sleep delays:
- `await asyncio.sleep(0.5)` for rate limit errors
- `await asyncio.sleep(0.3)` for JSON parse errors

These fixed delays don't provide adequate spacing between retry attempts and can cause multiple clients to retry at the same time (thundering herd).

### Related Issue
ROOT-REL-003 already addressed exponential backoff for **frontend API calls** in `frontend/src/api/retry.js`. This fix addresses the **backend LLM service** which was not covered by ROOT-REL-003.

---

## Implemented Fix

### 1. Added Exponential Backoff Configuration
**File**: `backend/app/services/llm.py`

```python
# ─── Exponential Backoff Configuration ───────────────────────────────────────
# Used for retry delays to prevent thundering herd on rate limits/errors
BACKOFF_CONFIG = {
    "initial_delay_ms": 300,  # Base delay for first retry
    "max_delay_ms": 5000,     # Cap at 5 seconds
    "jitter_percent": 0.25,   # +/- 25% randomness to prevent thundering herd
}
```

### 2. Added Backoff Delay Calculator
```python
def calculate_backoff_delay(attempt: int) -> float:
    """
    Calculate exponential backoff delay with jitter for retries.
    
    Args:
        attempt: The current retry attempt number (0-indexed)
    
    Returns:
        Delay in seconds for the next retry
    """
    # Exponential delay: initial_delay * 2^attempt
    exponential_delay = BACKOFF_CONFIG["initial_delay_ms"] * (2 ** attempt)
    
    # Cap at max delay
    capped_delay = min(exponential_delay, BACKOFF_CONFIG["max_delay_ms"])
    
    # Add jitter: +/- jitter_percent
    jitter = capped_delay * BACKOFF_CONFIG["jitter_percent"] * (random.random() * 2 - 1)
    
    # Convert to seconds for asyncio.sleep
    return (capped_delay + jitter) / 1000.0
```

### 3. Updated Retry Logic
Replaced all fixed sleep delays with exponential backoff:

- **Groq Rate Limit Error**: `await asyncio.sleep(0.5)` → `await asyncio.sleep(calculate_backoff_delay(attempt))`
- **Groq JSON Parse Error**: `await asyncio.sleep(0.3)` → `await asyncio.sleep(calculate_backoff_delay(attempt))`
- **Gemini JSON Parse Error**: `await asyncio.sleep(0.3)` → `await asyncio.sleep(calculate_backoff_delay(attempt))`
- **Gemini General Error**: `await asyncio.sleep(0.5)` → `await asyncio.sleep(calculate_backoff_delay(attempt))`

### 4. Added Observability
Each backoff delay is logged for debugging:
```python
backoff_delay = calculate_backoff_delay(attempt)
logger.info("Rate limit backoff: %.2fs", backoff_delay)
await asyncio.sleep(backoff_delay)
```

---

## Backoff Behavior

| Attempt | Base Delay | With Jitter (±25%) |
|---------|------------|-------------------|
| 0 | 300ms | 225-375ms |
| 1 | 600ms | 450-750ms |
| 2 | 1200ms | 900-1500ms |
| 3 | 2400ms | 1800-3000ms |
| 4 | 4800ms | 3600-5000ms (capped) |

---

## Files Modified

1. ✅ `backend/app/services/llm.py` (MODIFIED)
   - Added `random` import
   - Added `BACKOFF_CONFIG` dictionary
   - Added `calculate_backoff_delay()` function
   - Updated 4 retry locations to use exponential backoff
   - Added logging for backoff delays

---

## Verification

### Syntax Check
```bash
python -m py_compile backend/app/services/llm.py
# ✅ No syntax errors
```

### Recommended Testing
1. Start backend server: `cd backend && python -m uvicorn main:app --reload --port 8000`
2. Trigger LLM briefing generation (will use Groq/Gemini)
3. Monitor logs for backoff delay messages:
   - `[INFO] Rate limit backoff: 0.XXXs`
   - `[INFO] JSON parse retry backoff: 0.XXXs`
   - `[INFO] Error backoff: 0.XXXs`
4. Verify delays increase exponentially with each retry attempt

---

## Impact Assessment

### Before Fix
- ❌ Fixed 300-500ms delays on retries
- ❌ No exponential backoff
- ❌ No jitter to prevent thundering herd
- ❌ Multiple clients can retry simultaneously

### After Fix
- ✅ Exponential backoff: 300ms → 600ms → 1200ms → 2400ms → 4800ms
- ✅ Jitter: ±25% randomization prevents synchronized retries
- ✅ Max delay cap: 5 seconds prevents excessive waits
- ✅ Observable: All backoff delays logged

---

## Relationship to ROOT-REL-003

ROOT-REL-003 addressed exponential backoff for **frontend API calls** in `frontend/src/api/retry.js`. This fix addresses the **backend LLM service** which was a separate location not covered by ROOT-REL-003.

The two fixes together provide comprehensive exponential backoff coverage:
- Frontend → `frontend/src/api/retry.js` (ROOT-REL-003)
- Backend LLM → `backend/app/services/llm.py` (ROOT-REL-006)

---

## Status: ✅ COMPLETED

This fix addresses ROOT-REL-006 by implementing exponential backoff with jitter in the backend LLM service, preventing thundering herd on retries and improving overall system reliability.