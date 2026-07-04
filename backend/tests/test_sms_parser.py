"""
Tests for the SMS fallback scaffolding (FEATURES_ROADMAP §3.1). Only the
vendor-independent parser and default gateway are exercised here — there is
no live webhook endpoint to test since that part is deliberately not built
(see app/services/sms.py's module docstring).
"""
import pytest

from app.services.sms import NullSmsGateway, SmsParseError, parse_inbound_sms


def test_parses_valid_message():
    result = parse_inbound_sms("TRIAGE 34 F chest_pain,breathlessness")
    assert result.patient_age == 34
    assert result.patient_sex == "female"
    assert result.symptoms == ["chest_pain", "breathlessness"]


def test_case_insensitive_keyword_and_sex():
    result = parse_inbound_sms("triage 5 m high_fever")
    assert result.patient_sex == "male"
    assert result.symptoms == ["high_fever"]


def test_tolerates_surrounding_whitespace():
    result = parse_inbound_sms("  TRIAGE 60 F severe_bleeding  ")
    assert result.patient_age == 60


def test_rejects_missing_keyword():
    with pytest.raises(SmsParseError):
        parse_inbound_sms("34 F chest_pain")


def test_rejects_unknown_symptom():
    with pytest.raises(SmsParseError):
        parse_inbound_sms("TRIAGE 34 F not_a_real_symptom")


def test_rejects_missing_symptoms():
    with pytest.raises(SmsParseError):
        parse_inbound_sms("TRIAGE 34 F")


def test_rejects_out_of_range_age():
    with pytest.raises(SmsParseError):
        parse_inbound_sms("TRIAGE 999 F chest_pain")


def test_rejects_invalid_sex_token():
    with pytest.raises(SmsParseError):
        parse_inbound_sms("TRIAGE 34 X chest_pain")


def test_rejects_empty_body():
    with pytest.raises(SmsParseError):
        parse_inbound_sms("")


def test_error_carries_actionable_reason():
    with pytest.raises(SmsParseError) as exc:
        parse_inbound_sms("garbage")
    assert "TRIAGE" in exc.value.reason


def test_null_gateway_does_not_raise():
    NullSmsGateway().send("+911234567890", "test message")
