"""
SMS-based zero-connectivity fallback submission (FEATURES_ROADMAP §3.1) —
SCAFFOLDING ONLY, per explicit user decision. This module provides exactly
the parts that do NOT require a vendor/product decision: a pluggable
send-side gateway interface and a strict fixed-format inbound-message
parser, both fully testable in isolation.

Deliberately NOT built here: a live inbound webhook wired to case_records.
That needs two decisions this module cannot make on its own — (1) which SMS
aggregator (determines the actual webhook payload shape and that vendor's
signature-verification scheme, e.g. Twilio's HMAC signature), and (2) the
trust model for a channel that can't carry a Bearer JWT (the natural
candidate — authenticating by a pre-registered ASHA worker phone number —
is a real design change to the auth model and needs its own security review
before it goes live, not something to slip in as a side effect of scaffolding).
"""
from __future__ import annotations

import base64
import logging
import math
import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.models.schemas import ALLOWED_SYMPTOMS

logger = logging.getLogger("vitalnet")


class SmsGateway(Protocol):
    """
    Send-side abstraction. A real vendor adapter (Twilio, MSG91, an Indian
    licensed SMS aggregator, etc.) implements `send` and nothing else in
    this module needs to change.
    """

    def send(self, to: str, body: str) -> None: ...


class NullSmsGateway:
    """
    Default gateway: logs what would be sent instead of calling a real
    aggregator. Mirrors app/services/push.py's no-op-when-unconfigured
    pattern — safe to wire in now, becomes a real send once a vendor is
    chosen and a concrete SmsGateway implementation replaces this one.
    """

    def send(self, to: str, body: str) -> None:
        logger.info("SMS gateway not configured — would send to %s: %s", to, body)


@dataclass
class ParsedSmsIntake:
    patient_age: int
    patient_sex: str
    symptoms: list[str]


class SmsParseError(Exception):
    """Carries a human-readable reason suitable for relaying back to the
    sender via an auto-reply — a malformed SMS should never be silently
    dropped without telling the sender why."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


SMS_FORMAT_HELP = (
    "Invalid format. Send: TRIAGE <age> <M/F> <symptom1,symptom2,...>. "
    "Example: TRIAGE 34 F chest_pain,breathlessness"
)

_SEX_MAP = {"M": "male", "F": "female"}

# TRIAGE <age> <M|F> <symptom_id[,symptom_id...]>
# Deliberately strict (reject rather than guess) — a misparsed field in a
# clinical triage context is worse than a rejected message with a clear
# auto-reply telling the sender the correct format.
_SMS_PATTERN = re.compile(
    r"^\s*TRIAGE\s+(?P<age>\d{1,3})\s+(?P<sex>[MF])\s+(?P<symptoms>[a-zA-Z_,]+)\s*$",
    re.IGNORECASE,
)


def parse_inbound_sms(body: str) -> ParsedSmsIntake:
    """
    Parses the fixed SMS format into a minimal triage-able intake (age, sex,
    symptom ids — the reduced feature set the spec identifies as already
    supported by ClinicalFeatureEngineer's missing-vitals handling, so this
    is an intake/transport problem, not a triage-logic one). Raises
    SmsParseError — never a bare exception — on any malformed input.
    """
    match = _SMS_PATTERN.match(body or "")
    if not match:
        raise SmsParseError(SMS_FORMAT_HELP)

    age = int(match.group("age"))
    if not (0 <= age <= 120):
        raise SmsParseError(f"Age must be 0-120. {SMS_FORMAT_HELP}")

    sex = _SEX_MAP[match.group("sex").upper()]

    symptom_ids = [s for s in match.group("symptoms").lower().split(",") if s]
    if not symptom_ids:
        raise SmsParseError(f"At least one symptom is required. {SMS_FORMAT_HELP}")

    unknown = set(symptom_ids) - ALLOWED_SYMPTOMS
    if unknown:
        raise SmsParseError(f"Unrecognised symptom(s): {sorted(unknown)}. {SMS_FORMAT_HELP}")

    return ParsedSmsIntake(patient_age=age, patient_sex=sex, symptoms=symptom_ids)


# ── 28-Byte Authenticated Compact Emergency SMS Codec (ADR §51) ───────────────

ALLOWED_SYMPTOMS_ORDER = [
    "chest_pain",
    "breathlessness",
    "altered_consciousness",
    "severe_bleeding",
    "seizure",
    "high_fever",
    "severe_abdominal_pain",
    "persistent_vomiting",
    "severe_headache",
    "weakness_one_side",
    "difficulty_speaking",
    "swelling_face_throat",
]

SYMPTOM_ALIASES = {
    "abdominal_pain": "severe_abdominal_pain",
    "severe_abdominal_pain": "severe_abdominal_pain",
    "headache": "severe_headache",
    "severe_headache": "severe_headache",
    "vomiting_diarrhea": "persistent_vomiting",
    "persistent_vomiting": "persistent_vomiting",
    "focal_weakness": "weakness_one_side",
    "weakness_one_side": "weakness_one_side",
}

CRC24_INIT = 0xb704ce
CRC24_POLY = 0x1864cfb


def compute_crc24(data: bytes, length: int | None = None) -> int:
    """Computes CRC-24-Radix64 over byte sequence."""
    if length is None:
        length = len(data)
    crc = CRC24_INIT
    for i in range(length):
        crc ^= data[i] << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= CRC24_POLY
    return crc & 0xffffff


_crc24 = compute_crc24


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _base64url_decode(s: str) -> bytes:
    pad = (4 - len(s) % 4) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)


_E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_e164_phone_number(phone: str) -> bool:
    """Validates E.164 phone numbers (+<country_code><number>, 2..15 digits total)."""
    if not phone or not isinstance(phone, str):
        return False
    return bool(_E164_PATTERN.match(phone.strip()))


def uuid_to_bytes(uuid_str: str) -> bytes:
    clean = (uuid_str or "").replace("-", "")
    if len(clean) != 32:
        clean = clean.zfill(32)[:32]
    try:
        return bytes.fromhex(clean)
    except ValueError:
        return b"\x00" * 16


def bytes_to_uuid(b: bytes) -> str:
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def encode_emergency_sms(input_data: dict) -> str:
    """
    Encodes SMS frame input into 28-byte binary frame with CRC24 and returns 'VN1:<Base64url>'.
    Accepts age, sex, and tier aliases (BUG-22, BUG-37, BUG-44, BUG-46).
    """
    buf = bytearray(28)

    # Bytes 0..15: Client UUID
    client_id = input_data.get("client_id") or input_data.get("clientId") or "00000000-0000-0000-0000-000000000000"
    uuid_b = uuid_to_bytes(str(client_id))
    buf[0:16] = uuid_b[:16]

    # Byte 16: Version (bits 7..5), Sex (bits 4..3), Pregnant (bit 2), Tier (bits 1..0)
    version = 1
    raw_sex = input_data.get("patient_sex") or input_data.get("patientSex") or input_data.get("sex") or "male"
    norm_sex = str(raw_sex).lower()
    sex_code = 1 if norm_sex == "female" else (2 if norm_sex == "other" else 0)

    is_pregnant = bool(
        input_data.get("is_pregnant")
        if input_data.get("is_pregnant") is not None
        else input_data.get("isPregnant")
    )
    preg_code = 1 if is_pregnant else 0

    raw_tier = input_data.get("triage_level") or input_data.get("triageTier") or input_data.get("tier") or "ROUTINE"
    norm_tier = str(raw_tier).upper()
    tier_code = 2 if norm_tier == "EMERGENCY" else (1 if norm_tier == "URGENT" else 0)

    buf[16] = ((version & 0x7) << 5) | ((sex_code & 0x3) << 3) | ((preg_code & 0x1) << 2) | (tier_code & 0x3)

    # Byte 17: Age (0..120 years, 200..223 for sub-year infant 0..23 months, or 254 legacy)
    raw_age_months = input_data.get("age_months") if input_data.get("age_months") is not None else input_data.get("ageMonths")
    raw_age = (
        input_data.get("patient_age")
        if input_data.get("patient_age") is not None
        else (input_data.get("patientAge") if input_data.get("patientAge") is not None else input_data.get("age"))
    )

    if raw_age_months is not None and 0 <= float(raw_age_months) <= 23:
        buf[17] = 200 + int(round(float(raw_age_months)))
    elif raw_age is not None and 0 < float(raw_age) < 1:
        derived_months = min(23, max(0, int(round(float(raw_age) * 12))))
        buf[17] = 200 + derived_months
    else:
        age_val = int(round(float(raw_age))) if raw_age is not None else 0
        buf[17] = max(0, min(120, age_val))

    # Bytes 18..19: Symptom Mask
    mask = 0
    symptoms = input_data.get("symptoms") or []
    if isinstance(symptoms, (list, tuple, set)):
        for s in symptoms:
            canonical = SYMPTOM_ALIASES.get(str(s), str(s))
            if canonical in ALLOWED_SYMPTOMS_ORDER:
                idx = ALLOWED_SYMPTOMS_ORDER.index(canonical)
                if 0 <= idx < 12:
                    mask |= (1 << idx)
    buf[18] = (mask >> 8) & 0xff
    buf[19] = mask & 0xff

    # Byte 20: SBP
    sbp = input_data.get("bp_systolic") if input_data.get("bp_systolic") is not None else input_data.get("bpSystolic")
    if sbp is not None and 21 <= sbp <= 270:
        buf[20] = max(1, min(250, int(round(sbp)) - 20))
    else:
        buf[20] = 0

    # Byte 21: DBP
    dbp = input_data.get("bp_diastolic") if input_data.get("bp_diastolic") is not None else input_data.get("bpDiastolic")
    if dbp is not None and 1 <= dbp <= 200:
        buf[21] = max(1, min(200, int(round(dbp))))
    else:
        buf[21] = 0

    # Byte 22: SpO2
    spo2 = input_data.get("spo2")
    if spo2 is not None and 50 <= spo2 <= 100:
        buf[22] = max(50, min(100, int(round(spo2))))
    else:
        buf[22] = 0

    # Byte 23: HR
    hr = input_data.get("heart_rate") if input_data.get("heart_rate") is not None else input_data.get("heartRate")
    if hr is not None and 10 <= hr <= 250:
        buf[23] = max(10, min(250, int(round(hr))))
    else:
        buf[23] = 0

    # Byte 24: Temperature
    temp = input_data.get("temperature")
    if temp is not None and 25.1 <= temp <= 45.0:
        buf[24] = max(1, min(200, int(round((temp - 25.0) * 10))))
    else:
        buf[24] = 0

    # Bytes 25..27: CRC24
    crc = compute_crc24(bytes(buf), 25)
    buf[25] = (crc >> 16) & 0xff
    buf[26] = (crc >> 8) & 0xff
    buf[27] = crc & 0xff

    return f"VN1:{_base64url_encode(bytes(buf))}"


encode_emergency_sms_frame = encode_emergency_sms


def decode_emergency_sms(frame_text: str) -> dict:
    """
    Decodes 'VN1:<Base64url>' into structured emergency SMS payload verifying CRC24.
    """
    if not frame_text or not isinstance(frame_text, str):
        raise ValueError("InvalidSmsFrame: Frame text must be non-empty string")

    trimmed = frame_text.strip()
    direct_match = re.search(r"^VN1:([A-Za-z0-9_-]{37,39})$", trimmed)
    if direct_match:
        base64_part = direct_match.group(1)
    else:
        embedded = re.search(r"(?:^|[\s\[(])VN1:([A-Za-z0-9_-]{37,39})(?=[\])\s]|$)", trimmed)
        if embedded:
            base64_part = embedded.group(1)
        else:
            if "VN1:" in frame_text:
                raise ValueError("InvalidSmsFrame: Malformed or truncated VN1 frame")
            raise ValueError("InvalidSmsFrame: No VN1 emergency frame found in SMS body")

    buf = _base64url_decode(base64_part)
    if len(buf) != 28:
        raise ValueError(f"InvalidSmsFrame: Expected 28 bytes binary, got {len(buf)}")

    expected_crc = compute_crc24(buf, 25)
    actual_crc = (buf[25] << 16) | (buf[26] << 8) | buf[27]
    if expected_crc != actual_crc:
        raise ValueError(f"CRC24 integrity check failed: expected 0x{expected_crc:x}, got 0x{actual_crc:x}")

    client_id = bytes_to_uuid(buf[0:16])
    flags = buf[16]
    version = (flags >> 5) & 0x7
    if version != 1:
        raise ValueError(f"Unsupported VN1 frame version: {version}")

    sex_code = (flags >> 3) & 0x3
    preg_code = (flags >> 2) & 0x1
    tier_code = flags & 0x3

    patient_sex = "female" if sex_code == 1 else ("other" if sex_code == 2 else "male")
    is_pregnant = (preg_code == 1)
    triage_tier = "EMERGENCY" if tier_code == 2 else ("URGENT" if tier_code == 1 else "ROUTINE")

    raw_age_byte = buf[17]
    if 200 <= raw_age_byte <= 223:
        age_months = raw_age_byte - 200
        patient_age = age_months // 12
    elif raw_age_byte == 254:
        patient_age = 0
        age_months = 6
    else:
        patient_age = raw_age_byte
        age_months = None

    mask = (buf[18] << 8) | buf[19]
    symptoms = []
    for i in range(12):
        if (mask & (1 << i)) != 0:
            symptoms.append(ALLOWED_SYMPTOMS_ORDER[i])

    bp_systolic = None if buf[20] == 0 else (buf[20] + 20)
    bp_diastolic = None if buf[21] == 0 else buf[21]
    spo2 = None if buf[22] == 0 else buf[22]
    heart_rate = None if buf[23] == 0 else buf[23]
    temperature = None if buf[24] == 0 else round(25.0 + buf[24] / 10.0, 1)

    return {
        "clientId": client_id,
        "client_id": client_id,
        "patientAge": patient_age,
        "patient_age": patient_age,
        "age": patient_age,
        "ageMonths": age_months,
        "age_months": age_months,
        "patientSex": patient_sex,
        "patient_sex": patient_sex,
        "sex": patient_sex,
        "isPregnant": is_pregnant,
        "is_pregnant": is_pregnant,
        "triageTier": triage_tier,
        "triage_level": triage_tier,
        "tier": triage_tier,
        "symptoms": symptoms,
        "bpSystolic": bp_systolic,
        "bp_systolic": bp_systolic,
        "bpDiastolic": bp_diastolic,
        "bp_diastolic": bp_diastolic,
        "spo2": spo2,
        "heartRate": heart_rate,
        "heart_rate": heart_rate,
        "temperature": temperature,
        "version": version,
    }


decode_emergency_sms_frame = decode_emergency_sms

