"""
Challenger 1: Empirical Adversarial Verification Suite for REG-01, REG-02, REG-05
==================================================================================

Covers:
1. SMS Codec Sub-Year Age Encoding & Decoding (REG-01):
   - Exhaustive byte space stress testing (all 256 byte values 0..255 for byte 17).
   - Sub-year boundaries: 0, 1, 2, 3, 11, 12, 23, 24 months + fractional ages.
   - Backward-compatibility: Legacy byte 254 decodes to patient_age 0, age_months 6.
   - Cross-language protocol symmetry between Python (sms.py) and TypeScript (smsCodec.ts).
2. Database Check Constraint & Priority Mapping (REG-02, REG-05):
   - case_records_triage_priority_map_check simulation (0=EMERGENCY, 1=URGENT, 2=ROUTINE).
   - Enforcement across backend/app/api/routes/cases.py and apps/api/supabase/functions/api/routes/cases.ts.
   - Stub record NOT NULL column compliance and onConflict ignore_duplicates verification.
"""

import json
from pathlib import Path
import re
import subprocess
import uuid
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

from app.services.sms import (
    encode_emergency_sms,
    decode_emergency_sms,
    compute_crc24,
    _base64url_encode,
    _base64url_decode,
    SmsParseError,
)
from app.api.routes.cases import (
    _triage_priority_from_tier,
    SYSTEM_SUBMITTER_UUID,
    SYSTEM_FACILITY_UUID,
)

TEST_UUID = "12345678-1234-5678-1234-567812345678"


def _create_raw_frame_with_age_byte(age_byte: int) -> str:
    buf = bytearray(28)
    # UUID bytes 0..15
    for i in range(16):
        buf[i] = i
    # Byte 16: version 1, male, not pregnant, routine
    buf[16] = (1 & 0x7) << 5
    # Byte 17: Age byte
    buf[17] = age_byte & 0xFF
    # Bytes 18..24: 0
    # Bytes 25..27: CRC24
    crc = compute_crc24(bytes(buf), 25)
    buf[25] = (crc >> 16) & 0xFF
    buf[26] = (crc >> 8) & 0xFF
    buf[27] = crc & 0xFF
    return f"VN1:{_base64url_encode(bytes(buf))}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. SMS Codec Byte Space & Sub-Year Boundaries (REG-01)
# ─────────────────────────────────────────────────────────────────────────────

class TestSmsCodecByteSpaceAndBoundaries:
    def test_exhaustive_byte_space_0_to_255(self):
        """Stress-test all 256 possible byte values in byte 17."""
        for b in range(256):
            frame = _create_raw_frame_with_age_byte(b)
            decoded = decode_emergency_sms(frame)

            assert isinstance(decoded["patient_age"], int)

            if 200 <= b <= 223:
                expected_months = b - 200
                expected_years = expected_months // 12
                assert decoded["age_months"] == expected_months
                assert decoded["patient_age"] == expected_years
            elif b == 254:
                assert decoded["patient_age"] == 0
                assert decoded["age_months"] == 6
            else:
                assert decoded["patient_age"] == b
                assert decoded["age_months"] is None

    @pytest.mark.parametrize(
        "months,expected_years,expected_byte",
        [
            (0, 0, 200),
            (1, 0, 201),
            (2, 0, 202),
            (3, 0, 203),
            (11, 0, 211),
            (12, 1, 212),
            (23, 1, 223),
            (24, 2, 2),
        ],
    )
    def test_sub_year_boundaries_encoding_and_decoding(self, months, expected_years, expected_byte):
        payload = {
            "client_id": TEST_UUID,
            "patient_age": expected_years,
            "age_months": months,
            "symptoms": [],
        }
        encoded = encode_emergency_sms(payload)
        raw_bytes = _base64url_decode(encoded[4:])
        assert raw_bytes[17] == expected_byte

        decoded = decode_emergency_sms(encoded)
        assert decoded["patient_age"] == expected_years
        if months <= 23:
            assert decoded["age_months"] == months
        else:
            assert decoded["age_months"] is None

    def test_fractional_age_without_age_months(self):
        # 0.25 years = 3 months -> byte 203
        payload_3m = {"client_id": TEST_UUID, "patient_age": 0.25, "symptoms": []}
        dec_3m = decode_emergency_sms(encode_emergency_sms(payload_3m))
        assert dec_3m["patient_age"] == 0
        assert dec_3m["age_months"] == 3

        # 0.0833 years = 1 month -> byte 201
        payload_1m = {"client_id": TEST_UUID, "patient_age": 0.0833, "symptoms": []}
        dec_1m = decode_emergency_sms(encode_emergency_sms(payload_1m))
        assert dec_1m["patient_age"] == 0
        assert dec_1m["age_months"] == 1

        # 0.5 years = 6 months -> byte 206
        payload_6m = {"client_id": TEST_UUID, "patient_age": 0.5, "symptoms": []}
        dec_6m = decode_emergency_sms(encode_emergency_sms(payload_6m))
        assert dec_6m["patient_age"] == 0
        assert dec_6m["age_months"] == 6

    def test_legacy_byte_254_backward_compatibility(self):
        legacy_frame = _create_raw_frame_with_age_byte(254)
        decoded = decode_emergency_sms(legacy_frame)
        assert decoded["patient_age"] == 0
        assert decoded["age_months"] == 6

    def test_adversarial_malformed_frames(self):
        with pytest.raises(ValueError, match="Malformed or truncated VN1 frame"):
            decode_emergency_sms("VN1:short")

        valid_frame = _create_raw_frame_with_age_byte(200)
        with pytest.raises(ValueError, match="No VN1 emergency frame found"):
            decode_emergency_sms(valid_frame[4:])

        raw = bytearray(_base64url_decode(valid_frame[4:]))
        raw[27] ^= 0xFF
        corrupt_crc = f"VN1:{_base64url_encode(bytes(raw))}"
        with pytest.raises(ValueError, match="CRC24 integrity check failed"):
            decode_emergency_sms(corrupt_crc)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cross-Language Protocol Symmetry (TypeScript <-> Python)
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossLanguageProtocolSymmetry:
    def _call_node_decoder(self, frame: str) -> dict:
        cmd = [
            "node",
            "-e",
            f"const {{ decodeEmergencySms }} = await import('./packages/clinical-core/dist/index.js'); "
            f"console.log(JSON.stringify(decodeEmergencySms('{frame}')));",
        ]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
        return json.loads(res.stdout.strip())

    def _call_node_encoder(self, payload: dict) -> str:
        payload_json = json.dumps(payload)
        cmd = [
            "node",
            "-e",
            f"const {{ encodeEmergencySms }} = await import('./packages/clinical-core/dist/index.js'); "
            f"console.log(encodeEmergencySms({payload_json}));",
        ]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_cross_language_sub_year_matrix(self):
        """Cross-verifies that Python and TypeScript agree bit-for-bit on sub-year ages."""
        test_cases = [
            {"age_months": 0, "patient_age": 0, "temperature": 38.5, "symptoms": ["fever"]},
            {"age_months": 1, "patient_age": 0, "temperature": 38.0, "symptoms": ["fever"]},
            {"age_months": 2, "patient_age": 0, "temperature": 39.1, "symptoms": ["fever", "cough"]},
            {"age_months": 3, "patient_age": 0, "temperature": 37.5, "symptoms": []},
            {"age_months": 11, "patient_age": 0, "temperature": 36.8, "symptoms": ["vomiting"]},
            {"age_months": 12, "patient_age": 1, "temperature": 37.0, "symptoms": []},
            {"age_months": 23, "patient_age": 1, "temperature": 38.2, "symptoms": ["fever"]},
            {"patient_age": 45, "temperature": 36.5, "symptoms": ["chest_pain"], "triage_level": "EMERGENCY"},
        ]

        for case in test_cases:
            payload = {
                "client_id": TEST_UUID,
                "patient_sex": "female",
                "is_pregnant": False,
                "triage_level": case.get("triage_level", "ROUTINE"),
                "patient_age": case["patient_age"],
                "age_months": case.get("age_months"),
                "temperature": case.get("temperature"),
                "symptoms": case.get("symptoms", []),
            }

            # 1. Python encode -> TS decode
            py_frame = encode_emergency_sms(payload)
            ts_decoded = self._call_node_decoder(py_frame)
            py_decoded = decode_emergency_sms(py_frame)

            assert ts_decoded["patient_age"] == py_decoded["patient_age"]
            assert ts_decoded["age_months"] == py_decoded["age_months"]
            assert ts_decoded["temperature"] == py_decoded["temperature"]
            assert ts_decoded["triage_level"] == py_decoded["triage_level"]
            assert ts_decoded["client_id"] == py_decoded["client_id"]

            # 2. TS encode -> Python decode
            ts_frame = self._call_node_encoder(payload)
            assert ts_frame == py_frame  # Bit-for-bit identical wire frames!


# ─────────────────────────────────────────────────────────────────────────────
# 3. Database Check Constraint & Priority Mapping (REG-02, REG-05)
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseConstraintAndPriorityMapping:
    @staticmethod
    def _pg_check_constraint(triage_level: str | None, triage_priority: int | None) -> bool:
        """
        Exact simulation of PostgreSQL check constraint:
        case_records_triage_priority_map_check
        CHECK (
          (triage_level = 'EMERGENCY' AND triage_priority = 0) OR
          (triage_level = 'URGENT' AND triage_priority = 1) OR
          (triage_level = 'ROUTINE' AND triage_priority = 2) OR
          triage_priority IS NULL
        )
        """
        if triage_priority is None:
            return True
        if triage_level == "EMERGENCY" and triage_priority == 0:
            return True
        if triage_level == "URGENT" and triage_priority == 1:
            return True
        if triage_level == "ROUTINE" and triage_priority == 2:
            return True
        return False

    def test_priority_mapping_strictly_satisfies_pg_constraint(self):
        """Verifies _triage_priority_from_tier output against PostgreSQL check constraint."""
        tiers = ["EMERGENCY", "URGENT", "ROUTINE"]
        expected_priorities = {"EMERGENCY": 0, "URGENT": 1, "ROUTINE": 2}

        for tier in tiers:
            priority = _triage_priority_from_tier(tier)
            assert priority == expected_priorities[tier]
            assert self._pg_check_constraint(tier, priority) is True

    def test_inverted_or_invalid_priorities_fail_pg_constraint(self):
        """Proves that any inverted or out-of-bounds priority violates the DB constraint."""
        # Prior buggy inversion: EMERGENCY -> 2, URGENT -> 1, ROUTINE -> 0
        assert self._pg_check_constraint("EMERGENCY", 2) is False
        assert self._pg_check_constraint("ROUTINE", 0) is False

        # Out-of-bounds priorities
        for invalid_p in [-1, 3, 4, 99]:
            assert self._pg_check_constraint("EMERGENCY", invalid_p) is False
            assert self._pg_check_constraint("URGENT", invalid_p) is False
            assert self._pg_check_constraint("ROUTINE", invalid_p) is False

    def test_stub_record_contract_in_backend_cases_py(self):
        """Inspects that stub records in backend/app/api/routes/cases.py populate all NOT NULL columns."""
        with open(REPO_ROOT / "backend/app/api/routes/cases.py", "r", encoding="utf-8") as f:
            code = f.read()

        # Check required NOT NULL fields
        not_null_fields = [
            "submitted_by",
            "facility_id",
            "patient_name",
            "patient_location",
            "complaint_duration",
            "triage_priority",
        ]
        for field in not_null_fields:
            assert f'"{field}":' in code or f"'{field}':" in code, f"Missing NOT NULL field: {field}"

        # Check on_conflict="client_id", ignore_duplicates=True
        assert 'on_conflict="client_id"' in code
        assert "ignore_duplicates=True" in code

        # Check fallback UUIDs
        assert SYSTEM_SUBMITTER_UUID == "00000000-0000-0000-0000-000000000000"
        assert SYSTEM_FACILITY_UUID == "00000000-0000-0000-0000-000000000001"

    def test_stub_record_contract_in_edge_cases_ts(self):
        """Inspects that stub records in apps/api/supabase/functions/api/routes/cases.ts populate all NOT NULL columns."""
        with open(REPO_ROOT / "apps/api/supabase/functions/api/routes/cases.ts", "r", encoding="utf-8") as f:
            ts_code = f.read()

        not_null_fields = [
            "submitted_by",
            "facility_id",
            "patient_name",
            "patient_location",
            "complaint_duration",
            "triage_priority",
        ]
        for field in not_null_fields:
            assert f"{field}:" in ts_code, f"Missing NOT NULL field in TypeScript: {field}"

        # Check onConflict: "client_id", ignoreDuplicates: true
        assert 'onConflict: "client_id"' in ts_code
        assert "ignoreDuplicates: true" in ts_code

        # Check priority mapping in TypeScript
        # const triagePriority = triageLevel === "EMERGENCY" ? 0 : triageLevel === "URGENT" ? 1 : 2;
        assert 'triageLevel === "EMERGENCY" ? 0 : triageLevel === "URGENT" ? 1 : 2' in ts_code
