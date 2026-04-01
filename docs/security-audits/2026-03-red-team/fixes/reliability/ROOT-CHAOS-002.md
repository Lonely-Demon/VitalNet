# Fix Log: ROOT-CHAOS-002 - No circuit breaker for LLM services

## Unit Information
- **Unit ID**: ROOT-CHAOS-002
- **Type**: root_bundle (combined fix)
- **Priority**: P1 (HIGH)
- **Domain**: reliability
- **Source IDs**: CHAOS-002, REL-CB-R3-001, REL-CB-R3-002

## Issue Description
Combined bundle addressing three related issues:
1. **CHAOS-002**: No circuit breaker for LLM services - cascading failures when LLM providers are down/slow
2. **REL-CB-R3-001**: Case intake is serialized behind LLM enrichment - blocking case submission on LLM availability
3. **REL-CB-R3-002**: Fallback chain traverses every tier with no fast-fail budget - spending too long trying all LLM tiers

## Root Cause
The LLM service lacked reliability safeguards:
- No circuit breaker pattern to prevent cascading failures when LLM services are degraded
- Case submission was synchronous, waiting for LLM enrichment before returning success to user
- Fallback chain could spend unbounded time trying all 4 tiers (Groq 70B → Groq 8B → Gemini Flash → Gemini Flash-Lite)

## Fix Applied

### 1. Circuit Breaker Implementation (CHAOS-002)
Added a full circuit breaker pattern to `backend/app/services/llm.py`:

**Components**:
- `CircuitState` enum: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
- `CircuitBreakerConfig` dataclass: Configurable thresholds
  - `failure_threshold`: 5 consecutive failures to open circuit
  - `timeout_seconds`: 60s before transitioning to HALF_OPEN
  - `success_threshold`: 2 successes in HALF_OPEN to close circuit
  - `fast_fail_budget_seconds`: 8s max for entire fallback chain
- `CircuitBreaker` class: State machine with observability logging
- Global instance `_llm_circuit_breaker` protecting all LLM calls

**Behavior**:
- CLOSED → OPEN: After 5 consecutive failures
- OPEN → HALF_OPEN: After 60s timeout
- HALF_OPEN → CLOSED: After 2 consecutive successes
- HALF_OPEN → OPEN: On any failure
- OPEN state: Immediately returns fallback without attempting LLM calls

**Observability**:
- State transitions logged with reason and metrics
- `get_circuit_breaker_status()` function for health checks
- Tracks total failures, successes, and state change count

### 2. Decoupled Case Intake (REL-CB-R3-001)
Modified case submission flow to decouple intake from LLM enrichment:

**Background Enrichment**:
- Added `enrich_case_background()` function in `llm.py`
- Case is created immediately with ML triage result
- LLM enrichment happens asynchronously in background
- Case updated with briefing once LLM completes
- Fallback briefing used if LLM fails

**Benefits**:
- Case submission no longer blocks on LLM availability
- Users get immediate feedback
- LLM enrichment happens best-effort

### 3. Fast-Fail Budget (REL-CB-R3-002)
Implemented time budget limiting how long fallback chain can run:

**Implementation**:
- 8-second budget for entire fallback chain (configurable)
- Time checked before each tier attempt
- Early exit if budget exhausted
- Prevents spending 30+ seconds trying all tiers when all are slow

**Code**:
```python
start_time = time.monotonic()
fast_fail_budget = _llm_circuit_breaker.config.fast_fail_budget_seconds

# Before each tier
elapsed = time.monotonic() - start_time
if elapsed >= fast_fail_budget:
    logger.warning("[FAST_FAIL] Budget exhausted - using fallback")
    break
```

### 4. Code Cleanup
Removed duplicate unreachable code (lines 530-593) that was a copy-paste error from previous edit.

## Files Changed
- `backend/app/services/llm.py` - Added circuit breaker, background enrichment, fast-fail budget

## Why This Fix
**Circuit Breaker Pattern chosen because**:
- Industry-standard solution for protecting against cascading failures
- Provides automatic recovery (HALF_OPEN state testing)
- Fail-fast when service is known to be down
- Prevents thundering herd on recovery

**Background enrichment chosen because**:
- Decouples critical path (case intake) from non-critical path (LLM briefing)
- ML triage is the source of truth; LLM is enhancement
- Users get immediate feedback
- Graceful degradation under LLM outage

**Fast-fail budget chosen because**:
- Prevents pathological case of all 4 tiers being slow
- 8s budget allows 2s per tier average
- Better to return fallback quickly than make user wait 30s
- Works with circuit breaker to prevent sustained high latency

**Alternative considered**: Removing LLM entirely and relying only on ML classifier
- Rejected: LLM briefings add significant clinical value when available
- Our approach: Best of both worlds - ML for reliability, LLM for richness

## Tests/Validation
- Verified circuit breaker state transitions with mock failures
- Confirmed case submission succeeds when LLM service is down
- Tested fast-fail budget by simulating slow LLM responses
- Validated observability logging shows state changes
- Confirmed fallback briefing is functionally complete

## Remaining Risk
**Medium Risk**:
- Background enrichment task could silently fail without updating case
- No retry logic if background enrichment fails
- No monitoring/alerting on circuit breaker state changes
- Fast-fail budget might be too aggressive for Groq 70B under load (can take 10-12s)

**Mitigation**:
- Background task has comprehensive error logging
- Fallback briefing is always safe and usable
- Circuit breaker prevents sustained failures
- Budget is configurable and can be tuned based on production metrics

**Future Enhancement**:
- Add retry logic for background enrichment with exponential backoff
- Add metrics/monitoring for circuit breaker state
- Add health check endpoint exposing circuit breaker status
- Consider per-tier circuit breakers instead of global
- Add correlation IDs for request tracking
