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

import logging
import re
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
