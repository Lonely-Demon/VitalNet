"""
Tests for LLM circuit breaker and SBAR fallback briefing (BUG-26, BUG-27, BUG-64).
"""
import time
import pytest
from app.services.llm import (
    CircuitState,
    LlmCircuitBreaker,
    _fallback_briefing,
    generate_briefing,
    llm_circuit_breaker,
)


def test_circuit_breaker_state_machine():
    cb = LlmCircuitBreaker(failure_threshold=3, recovery_timeout=0.2)
    assert cb.state == CircuitState.CLOSED
    assert not cb.is_open()

    # Client errors do not increment upstream failure count (BUG-26)
    cb.record_failure(is_upstream=False)
    assert cb.consecutive_failures == 0
    assert cb.state == CircuitState.CLOSED

    # 1st and 2nd upstream failures
    cb.record_failure(is_upstream=True)
    assert cb.consecutive_failures == 1
    assert cb.state == CircuitState.CLOSED

    cb.record_failure(is_upstream=True)
    assert cb.consecutive_failures == 2
    assert cb.state == CircuitState.CLOSED

    # 3rd upstream failure trips to OPEN
    cb.record_failure(is_upstream=True)
    assert cb.consecutive_failures == 3
    assert cb.state == CircuitState.OPEN
    assert cb.is_open() is True

    # Cooldown transition to HALF_OPEN
    time.sleep(0.25)
    assert cb.is_open() is False
    assert cb.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 0


def test_fallback_briefing_separates_rule_mandated_vs_symptom_inferred():
    form_data = {
        "symptoms": ["chest_pain", "breathlessness"],
        "patient_age": 55,
        "patient_sex": "male",
    }
    triage_result = {
        "triage_level": "EMERGENCY",
        "risk_driver": "Chest pain with breathlessness",
        "low_confidence": False,
    }

    briefing = _fallback_briefing(triage_result, form_data)

    assert "rule_mandated_actions" in briefing
    assert "symptom_inferred_actions" in briefing
    assert len(briefing["rule_mandated_actions"]) > 0
    assert any("ABCDE" in act for act in briefing["rule_mandated_actions"])

    assert len(briefing["symptom_inferred_actions"]) > 0
    assert any("ECG" in act for act in briefing["symptom_inferred_actions"])

    # recommended_immediate_actions contains tagged items
    for act in briefing["recommended_immediate_actions"]:
        assert act.startswith("[Rule-Mandated]") or act.startswith("[Symptom-Inferred]")


@pytest.mark.asyncio
async def test_generate_briefing_fast_fails_when_circuit_open():
    llm_circuit_breaker.reset()
    # Trip circuit to OPEN
    llm_circuit_breaker.record_failure(is_upstream=True)
    llm_circuit_breaker.record_failure(is_upstream=True)
    llm_circuit_breaker.record_failure(is_upstream=True)
    assert llm_circuit_breaker.is_open() is True

    t0 = time.monotonic()
    res = await generate_briefing(
        {"symptoms": ["chest_pain"]},
        {"triage_level": "EMERGENCY", "risk_driver": "Chest pain"},
    )
    elapsed = time.monotonic() - t0

    assert elapsed < 0.1  # Fast fail without waiting for network timeout
    assert res["llm_status"] == "fallback"

    llm_circuit_breaker.reset()
