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


def test_validate_e164_phone_number():
    from app.services.sms import validate_e164_phone_number

    assert validate_e164_phone_number("+919876543210") is True
    assert validate_e164_phone_number("+14155552671") is True
    assert validate_e164_phone_number("9876543210") is False  # missing +
    assert validate_e164_phone_number("+0123456") is False  # cannot start with +0
    assert validate_e164_phone_number("invalid") is False
    assert validate_e164_phone_number("") is False
    assert validate_e164_phone_number(None) is False


def test_emergency_sms_codec_roundtrip_with_aliases():
    from app.services.sms import decode_emergency_sms, encode_emergency_sms

    input_payload = {
        "clientId": "12345678-1234-5678-1234-567812345678",
        "age": 45,
        "sex": "female",
        "isPregnant": True,
        "tier": "EMERGENCY",
        "symptoms": ["chest_pain", "breathlessness"],
        "bpSystolic": 140,
        "bpDiastolic": 90,
        "spo2": 95,
        "heartRate": 110,
        "temperature": 38.5,
    }

    frame = encode_emergency_sms(input_payload)
    assert frame.startswith("VN1:")

    decoded = decode_emergency_sms(frame)
    assert decoded["client_id"] == "12345678-1234-5678-1234-567812345678"
    assert decoded["patient_age"] == 45
    assert decoded["age"] == 45
    assert decoded["patient_sex"] == "female"
    assert decoded["sex"] == "female"
    assert decoded["is_pregnant"] is True
    assert decoded["triage_level"] == "EMERGENCY"
    assert decoded["tier"] == "EMERGENCY"
    assert "chest_pain" in decoded["symptoms"]
    assert "breathlessness" in decoded["symptoms"]
    assert decoded["bp_systolic"] == 140
    assert decoded["bp_diastolic"] == 90
    assert decoded["spo2"] == 95
    assert decoded["heart_rate"] == 110
    assert decoded["temperature"] == 38.5


def test_emergency_sms_sub_year_infant_encoding():
    from app.services.sms import (
        _base64url_decode,
        decode_emergency_sms,
        encode_emergency_sms,
    )

    # 1. 4-month-old infant: encodes to 200 + 4 = 204
    input_payload = {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "age_months": 4,
        "sex": "male",
        "tier": "URGENT",
        "symptoms": ["high_fever"],
    }
    frame = encode_emergency_sms(input_payload)
    raw_bytes = _base64url_decode(frame[4:])
    assert raw_bytes[17] == 204

    decoded = decode_emergency_sms(frame)
    assert decoded["patient_age"] == 0
    assert decoded["age_months"] == 4
    assert decoded["triage_level"] == "URGENT"

    # 2. 1-month-old neonate: encodes to 200 + 1 = 201
    neonate_frame = encode_emergency_sms({
        "client_id": "00000000-0000-0000-0000-000000000002",
        "age_months": 1,
        "sex": "female",
        "tier": "EMERGENCY",
        "symptoms": ["high_fever"],
        "temperature": 38.5,
    })
    neonate_raw = _base64url_decode(neonate_frame[4:])
    assert neonate_raw[17] == 201
    decoded_neonate = decode_emergency_sms(neonate_frame)
    assert decoded_neonate["patient_age"] == 0
    assert decoded_neonate["age_months"] == 1
    assert decoded_neonate["triage_level"] == "EMERGENCY"

    # 3. 18-month-old infant/toddler: encodes to 200 + 18 = 218
    toddler_frame = encode_emergency_sms({
        "client_id": "00000000-0000-0000-0000-000000000003",
        "age_months": 18,
        "sex": "female",
        "tier": "ROUTINE",
    })
    toddler_raw = _base64url_decode(toddler_frame[4:])
    assert toddler_raw[17] == 218
    decoded_toddler = decode_emergency_sms(toddler_frame)
    assert decoded_toddler["patient_age"] == 1
    assert decoded_toddler["age_months"] == 18

    # 4. Fractional year patient_age (0.25 -> 3 months): encodes to 200 + 3 = 203
    fractional_frame = encode_emergency_sms({
        "client_id": "00000000-0000-0000-0000-000000000004",
        "patient_age": 0.25,
        "sex": "male",
        "tier": "URGENT",
    })
    fractional_raw = _base64url_decode(fractional_frame[4:])
    assert fractional_raw[17] == 203
    decoded_fractional = decode_emergency_sms(fractional_frame)
    assert decoded_fractional["patient_age"] == 0
    assert decoded_fractional["age_months"] == 3


def test_emergency_sms_legacy_byte_254_decoding():
    from app.services.sms import (
        _base64url_decode,
        _base64url_encode,
        _crc24,
        decode_emergency_sms,
        encode_emergency_sms,
    )

    input_payload = {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "age": 25,
        "sex": "female",
        "tier": "URGENT",
        "symptoms": ["high_fever"],
    }
    frame = encode_emergency_sms(input_payload)
    b64 = frame[4:]
    raw_bytes = bytearray(_base64url_decode(b64))
    raw_bytes[17] = 254  # legacy byte 254 backward compatibility
    # recompute CRC24 over first 25 bytes
    crc = _crc24(bytes(raw_bytes[:25]))
    raw_bytes[25] = (crc >> 16) & 0xFF
    raw_bytes[26] = (crc >> 8) & 0xFF
    raw_bytes[27] = crc & 0xFF
    legacy_frame = f"VN1:{_base64url_encode(bytes(raw_bytes))}"

    decoded = decode_emergency_sms(legacy_frame)
    assert decoded["patient_age"] == 0
    assert decoded["age_months"] == 6
    assert decoded["triage_level"] == "URGENT"


def test_emergency_sms_crc_failure_raises():
    from app.services.sms import _base64url_decode, _base64url_encode, decode_emergency_sms, encode_emergency_sms

    input_payload = {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "age": 25,
        "sex": "female",
        "tier": "ROUTINE",
        "symptoms": ["headache"],
    }
    frame = encode_emergency_sms(input_payload)
    b64 = frame[4:]
    raw_bytes = bytearray(_base64url_decode(b64))
    raw_bytes[10] ^= 0xFF  # tamper byte
    tampered_frame = f"VN1:{_base64url_encode(bytes(raw_bytes))}"

    with pytest.raises(ValueError) as exc:
        decode_emergency_sms(tampered_frame)
    assert "CRC24 integrity check failed" in str(exc.value)

