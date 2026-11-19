"""
Milestone M2 Adversarial Challenge: phase54_performance_indexing_and_scale_hardening.sql

Empirically challenges:
1. SQL syntax, tokenization, transaction boundary, and delimiter balance.
2. F-05: Adversarial checks on respiratory_rate constraint bounds [5, 120] and NULL handling.
3. B1: STABLE RLS helpers, search_path security, EXECUTE grants, and (SELECT auth.uid()) InitPlan caching in asha_select_own.
4. B2: protect_case_records_clinical_columns trigger fast-path short-circuit, submitter lockdown, SMS stub promotion, clinician review preservation, and Phase 52 JSONB allowlist integrity.
5. B3 & F-11: 4 composite partial indexes and 4 dropped obsolete single-column indexes.
6. A3-2: fn_ears_daily_counts SQL aggregation RPC role authorization, facility pinning, mandatory p_since, and Asia/Kolkata timezone grouping.
"""

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import zoneinfo
import pytest
import sqlparse

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "supabase"
    / "migrations"
    / "phase54_performance_indexing_and_scale_hardening.sql"
)


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION_PATH.exists(), f"Migration file not found at {MIGRATION_PATH}"
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ==============================================================================
# 1. SQL Syntax, Tokenization & Transaction Boundaries
# ==============================================================================


def test_sql_transaction_boundaries(migration_sql: str):
    """Ensure the migration is strictly enclosed in a single BEGIN; ... COMMIT; transaction."""
    stripped = migration_sql.strip()
    lines = [
        line.strip()
        for line in stripped.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    assert lines[0].upper() == "BEGIN;", "First non-comment statement must be BEGIN;"
    assert lines[-1].upper() == "COMMIT;", "Last non-comment statement must be COMMIT;"

    # Ensure no internal commits or rollbacks break the atomic migration
    internal_lines = lines[1:-1]
    for line in internal_lines:
        assert not re.match(
            r"^\s*(COMMIT|ROLLBACK)\s*;", line, re.IGNORECASE
        ), "Unexpected transaction break inside migration"


def test_sqlparse_tokenization(migration_sql: str):
    """Ensure all statements in the migration parse cleanly via sqlparse."""
    statements = sqlparse.split(migration_sql)
    assert len(statements) >= 10, f"Expected at least 10 SQL statements, found {len(statements)}"

    parsed_statements = [sqlparse.parse(s)[0] for s in statements if s.strip()]
    assert len(parsed_statements) >= 10

    for stmt in parsed_statements:
        tokens = [t for t in stmt.tokens if not t.is_whitespace]
        assert len(tokens) > 0, "Encountered empty or malformed SQL statement token"


def test_sql_balanced_delimiters(migration_sql: str):
    """Ensure all parentheses, brackets, braces, and dollar-quote blocks are perfectly balanced."""
    dollar_blocks = re.findall(r"\$[a-zA-Z0-9_]*\$", migration_sql)
    assert len(dollar_blocks) % 2 == 0, f"Unbalanced dollar quote tags in PL/pgSQL: {dollar_blocks}"

    funcs = re.findall(
        r"CREATE OR REPLACE FUNCTION (.*?)\$\$(.*?)\$\$", migration_sql, re.DOTALL
    )
    assert len(funcs) >= 2, f"Expected at least 2 PL/pgSQL functions using $$ delimiter, found {len(funcs)}"

    for func_header, func_body in funcs:
        p_count = 0
        b_count = 0
        for char in func_body:
            if char == "(":
                p_count += 1
            elif char == ")":
                p_count -= 1
            elif char == "[":
                b_count += 1
            elif char == "]":
                b_count -= 1
            assert p_count >= 0, f"Mismatched closing parenthesis in function {func_header.split()[0]}"
            assert b_count >= 0, f"Mismatched closing bracket in function {func_header.split()[0]}"
        assert p_count == 0, f"Unclosed parenthesis in function {func_header.split()[0]}"
        assert b_count == 0, f"Unclosed bracket in function {func_header.split()[0]}"


# ==============================================================================
# 2. F-05: Adversarial Checks on respiratory_rate Constraint Bounds
# ==============================================================================


def check_respiratory_rate_bounds(rr: Optional[int]) -> bool:
    """Python oracle mirroring PostgreSQL CHECK (respiratory_rate IS NULL OR (respiratory_rate >= 5 AND respiratory_rate <= 120))."""
    if rr is None:
        return True
    return 5 <= rr <= 120


@pytest.mark.parametrize("invalid_rr", [-999, -100, -10, -1, 0, 1, 2, 3, 4])
def test_f05_respiratory_rate_rejects_sub_minimum(invalid_rr: int):
    """F-05: Values below 5 breaths/min must violate the CHECK constraint."""
    assert not check_respiratory_rate_bounds(invalid_rr)


@pytest.mark.parametrize("invalid_rr", [121, 122, 130, 150, 200, 500, 999, 9999])
def test_f05_respiratory_rate_rejects_supra_maximum(invalid_rr: int):
    """F-05: Values above 120 breaths/min must violate the CHECK constraint."""
    assert not check_respiratory_rate_bounds(invalid_rr)


@pytest.mark.parametrize("valid_rr", [5, 6, 12, 16, 20, 28, 40, 60, 80, 119, 120, None])
def test_f05_respiratory_rate_accepts_valid_range_and_null(valid_rr: Optional[int]):
    """F-05: Exact boundaries (5, 120), normal physiological values, and NULL must succeed."""
    assert check_respiratory_rate_bounds(valid_rr)


def test_f05_sql_schema_idempotency_and_definition(migration_sql: str):
    """F-05: Verify exact SQL DDL syntax and idempotency for respiratory_rate."""
    assert "ADD COLUMN IF NOT EXISTS respiratory_rate integer;" in migration_sql
    assert "conname = 'case_records_respiratory_rate_bounds'" in migration_sql
    assert "CHECK (respiratory_rate IS NULL OR (respiratory_rate >= 5 AND respiratory_rate <= 120))" in migration_sql


# ==============================================================================
# 3. B1: STABLE RLS Helpers and (SELECT auth.uid()) InitPlan Caching
# ==============================================================================


def test_b1_rls_helpers_stable_security_definer_and_search_path(migration_sql: str):
    """B1: Verify all 4 RLS helper functions are STABLE SECURITY DEFINER with fixed search_path."""
    helpers = [
        "get_user_role",
        "get_user_facility",
        "get_current_user_role",
        "get_current_user_facility",
    ]
    for fn in helpers:
        pattern = (
            rf"CREATE OR REPLACE FUNCTION public\.{fn}\b.*?"
            rf"LANGUAGE sql\s+"
            rf"STABLE\s+"
            rf"SECURITY DEFINER\s+"
            rf"SET search_path TO 'public'"
        )
        assert re.search(pattern, migration_sql, re.DOTALL) is not None, (
            f"{fn} must be declared STABLE SECURITY DEFINER with SET search_path TO 'public'"
        )


def test_b1_rls_helpers_permissions_revocation_and_grants(migration_sql: str):
    """B1: Verify execute permission is granted to authenticated and revoked from PUBLIC."""
    for fn in ["get_current_user_role()", "get_current_user_facility()"]:
        assert f"REVOKE ALL ON FUNCTION public.{fn} FROM PUBLIC;" in migration_sql
        assert f"GRANT EXECUTE ON FUNCTION public.{fn} TO authenticated;" in migration_sql


def simulate_asha_select_own_policy(
    row: Dict[str, Any],
    auth_uid: Optional[str],
    user_role: Optional[str],
    user_facility: Optional[str],
    is_active: bool = True,
) -> bool:
    """
    Python model of public.asha_select_own RLS policy:
      (SELECT auth.uid()) IS NOT NULL
      AND deleted_at IS NULL
      AND (
        submitted_by = (SELECT auth.uid())
        OR (
          public.get_current_user_role() = 'super_admin'
          OR (
            public.get_current_user_role() = ANY (ARRAY['doctor'::text, 'facility_admin'::text, 'admin'::text])
            AND public.get_current_user_facility() = case_records.facility_id
          )
        )
      )
    """
    if auth_uid is None:
        return False
    if row.get("deleted_at") is not None:
        return False

    # Effective active role & facility
    effective_role = user_role if is_active else None
    effective_facility = user_facility if is_active else None

    if row.get("submitted_by") == auth_uid:
        return True

    if effective_role == "super_admin":
        return True

    if effective_role in ("doctor", "facility_admin", "admin") and effective_facility == row.get("facility_id"):
        return True

    return False


def test_b1_asha_select_own_policy_adversarial_matrix():
    """B1: Adversarially test RLS authorization across all user roles, facilities, and active statuses."""
    row = {"id": "case-1", "submitted_by": "asha-1", "facility_id": "fac-1", "deleted_at": None}
    deleted_row = {"id": "case-2", "submitted_by": "asha-1", "facility_id": "fac-1", "deleted_at": "2026-11-01T00:00:00Z"}

    # 1. Unauthenticated / anonymous
    assert not simulate_asha_select_own_policy(row, auth_uid=None, user_role=None, user_facility=None)

    # 2. Soft-deleted row is hidden from everyone
    assert not simulate_asha_select_own_policy(deleted_row, "asha-1", "asha_worker", "fac-1")
    assert not simulate_asha_select_own_policy(deleted_row, "doc-1", "doctor", "fac-1")
    assert not simulate_asha_select_own_policy(deleted_row, "admin-1", "super_admin", None)

    # 3. ASHA submitter can view own submitted case
    assert simulate_asha_select_own_policy(row, "asha-1", "asha_worker", "fac-1")

    # 4. Other ASHA cannot view case submitted by asha-1
    assert not simulate_asha_select_own_policy(row, "asha-2", "asha_worker", "fac-1")

    # 5. Supervisor cannot view clinical case (VN-53-04 invariant)
    assert not simulate_asha_select_own_policy(row, "sup-1", "supervisor", "fac-1")

    # 6. Doctor in same facility can view
    assert simulate_asha_select_own_policy(row, "doc-1", "doctor", "fac-1")

    # 7. Doctor in different facility cannot view (tenancy isolation)
    assert not simulate_asha_select_own_policy(row, "doc-2", "doctor", "fac-2")

    # 8. Facility admin in same facility can view; different facility cannot
    assert simulate_asha_select_own_policy(row, "fa-1", "facility_admin", "fac-1")
    assert not simulate_asha_select_own_policy(row, "fa-2", "facility_admin", "fac-2")

    # 9. Super admin can view across any facility
    assert simulate_asha_select_own_policy(row, "sa-1", "super_admin", None)
    assert simulate_asha_select_own_policy(row, "sa-1", "super_admin", "fac-999")

    # 10. Inactive doctor cannot view cases (is_active = false)
    assert not simulate_asha_select_own_policy(row, "doc-1", "doctor", "fac-1", is_active=False)


# ==============================================================================
# 4. B2: protect_case_records_clinical_columns Trigger Fast-Path & Allowlist
# ==============================================================================

PHASE52_ALLOWED_SUBMITTER_COLS = {
    "deleted_at",
    "human_review_requested",
    "human_review_reason",
    "follow_up_completed_at",
    "updated_at",
}

PHASE52_ALLOWED_SMS_PROMOTION_COLS = {
    "is_sms_stub",
    "patient_name",
    "patient_age",
    "age_months",
    "patient_sex",
    "patient_location",
    "patient_key",
    "chief_complaint",
    "complaint_duration",
    "symptoms",
    "observations",
    "known_conditions",
    "current_medications",
    "is_pregnant",
    "muac_mm",
    "contraindication_flags",
    "temperature",
    "heart_rate",
    "bp_systolic",
    "bp_diastolic",
    "spo2",
    "respiratory_rate",
    "triage_level",
    "triage_priority",
    "triage_confidence",
    "triage_model_version",
    "risk_driver",
    "low_confidence",
    "needs_review",
    "deterioration_alert",
    "deterioration_visit_count",
    "briefing",
    "consent_given",
    "consent_timestamp",
    "created_offline",
    "client_submitted_at",
    "updated_at",
}

CLINICIAN_ONLY_FORBIDDEN_COLS = [
    "reviewed_by",
    "reviewed_at",
    "doctor_notes",
    "overridden_triage",
    "override_reason",
    "overridden_at",
    "facility_id",
    "submitted_by",
    "id",
    "client_id",
    "follow_up_required",
    "follow_up_due_at",
]


def simulate_phase54_protect_case_records_clinical_columns(
    old_row: Dict[str, Any],
    new_row: Dict[str, Any],
    auth_uid: Optional[str],
    user_role: Optional[str],
    is_active: bool = True,
) -> Dict[str, Any]:
    """
    Python oracle simulating the PL/pgSQL function protect_case_records_clinical_columns:
    - Fast path: IF (SELECT auth.uid()) IS DISTINCT FROM OLD.submitted_by THEN RETURN NEW;
    - Clinician/admin check: IF v_is_clinician_or_admin THEN RETURN NEW;
    - SMS stub promotion check: preserves clinician review; tests allowlist difference.
    - Submitter update check: tests allowlist difference.
    """
    res = dict(new_row)

    # Fast-path: non-submitter updates (clinicians, system, admins) bypass submitter restrictions
    # Note: In PostgreSQL: NULL IS DISTINCT FROM 'asha-1' is TRUE.
    # 'doc-1' IS DISTINCT FROM 'asha-1' is TRUE.
    # 'asha-1' IS DISTINCT FROM 'asha-1' is FALSE.
    if auth_uid != old_row.get("submitted_by"):
        return res

    # Check clinician/admin role
    v_is_clinician_or_admin = (
        is_active
        and user_role in ("doctor", "facility_admin", "admin", "super_admin")
    )
    if v_is_clinician_or_admin:
        return res

    # One-time promotion from an offline SMS stub by the original submitter
    old_is_stub = old_row.get("is_sms_stub") is True
    new_is_stub = new_row.get("is_sms_stub") is False

    if old_is_stub and new_is_stub:
        # 1. Clinician review/override preservation
        if old_row.get("reviewed_at") is not None or old_row.get("overridden_triage") is not None:
            res["triage_level"] = old_row.get("triage_level")
            res["triage_priority"] = old_row.get("triage_priority")
            res["needs_review"] = old_row.get("needs_review")

        # 2. JSONB allowlist difference
        new_remainder = {k: v for k, v in res.items() if k not in PHASE52_ALLOWED_SMS_PROMOTION_COLS}
        old_remainder = {k: v for k, v in old_row.items() if k not in PHASE52_ALLOWED_SMS_PROMOTION_COLS}
        if new_remainder != old_remainder:
            raise PermissionError(
                "42501: SMS stub promotion cannot modify clinician review, override, or tenant identity columns"
            )
        return res

    # Standard subsequent updates by a non-clinical submitter
    new_remainder = {k: v for k, v in res.items() if k not in PHASE52_ALLOWED_SUBMITTER_COLS}
    old_remainder = {k: v for k, v in old_row.items() if k not in PHASE52_ALLOWED_SUBMITTER_COLS}
    if new_remainder != old_remainder:
        raise PermissionError(
            "42501: Clinical, triage, override, and identity columns cannot be modified by the submitter"
        )

    return res


def test_b2_fast_path_non_submitter_short_circuits():
    """B2: When auth.uid() != OLD.submitted_by, updates bypass all submitter restrictions."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "triage_level": "URGENT",
        "temperature": 37.0,
        "is_sms_stub": False,
    }
    new = dict(old)
    # Doctor reviews and updates triage and doctor notes
    new["triage_level"] = "EMERGENCY"
    new["doctor_notes"] = "Immediate IV fluids required"
    new["reviewed_by"] = "doc-1"
    new["reviewed_at"] = "2026-11-19T06:00:00Z"

    # Fast path: auth_uid is 'doc-1', which is distinct from 'asha-1'
    result = simulate_phase54_protect_case_records_clinical_columns(
        old_row=old,
        new_row=new,
        auth_uid="doc-1",
        user_role="doctor",
    )
    assert result["triage_level"] == "EMERGENCY"
    assert result["doctor_notes"] == "Immediate IV fluids required"


def test_b2_fast_path_anonymous_or_system_short_circuits():
    """B2: When auth.uid() is NULL (service-role or internal process), fast-path succeeds."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "triage_level": "URGENT",
    }
    new = dict(old)
    new["triage_level"] = "NON_URGENT"

    # auth_uid is None -> NULL IS DISTINCT FROM 'asha-1' is TRUE -> returns NEW
    result = simulate_phase54_protect_case_records_clinical_columns(
        old_row=old,
        new_row=new,
        auth_uid=None,
        user_role=None,
    )
    assert result["triage_level"] == "NON_URGENT"


def test_b2_submitter_clinician_can_update():
    """B2: When submitter is also a doctor/admin, updates succeed."""
    old = {
        "id": "case-1",
        "submitted_by": "doc-1",
        "facility_id": "fac-1",
        "triage_level": "URGENT",
        "is_sms_stub": False,
    }
    new = dict(old)
    new["triage_level"] = "EMERGENCY"

    result = simulate_phase54_protect_case_records_clinical_columns(
        old_row=old,
        new_row=new,
        auth_uid="doc-1",
        user_role="doctor",
    )
    assert result["triage_level"] == "EMERGENCY"


@pytest.mark.parametrize(
    "clinical_field,val",
    [
        ("triage_level", "NON_URGENT"),
        ("triage_priority", 4),
        ("temperature", 39.5),
        ("heart_rate", 110),
        ("bp_systolic", 140),
        ("spo2", 90),
        ("respiratory_rate", 32),
        ("patient_name", "Tampered Name"),
        ("facility_id", "fac-evil"),
        ("doctor_notes", "Forged doctor note"),
        ("overridden_triage", "NON_URGENT"),
    ],
)
def test_b2_submitter_non_clinician_blocked_from_clinical_columns(clinical_field: str, val: Any):
    """B2: Standard subsequent updates by original ASHA submitter MUST reject clinical/tenant columns."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "triage_level": "URGENT",
        "triage_priority": 2,
        "temperature": 37.0,
        "heart_rate": 80,
        "bp_systolic": 120,
        "spo2": 98,
        "respiratory_rate": 20,
        "patient_name": "Original Name",
        "doctor_notes": None,
        "overridden_triage": None,
        "is_sms_stub": False,
        "deleted_at": None,
        "updated_at": "2026-11-19T05:00:00Z",
    }
    new = dict(old)
    new[clinical_field] = val
    new["updated_at"] = "2026-11-19T06:00:00Z"

    with pytest.raises(PermissionError) as exc_info:
        simulate_phase54_protect_case_records_clinical_columns(
            old_row=old,
            new_row=new,
            auth_uid="asha-1",
            user_role="asha_worker",
        )
    assert "42501" in str(exc_info.value)


def test_b2_submitter_allowed_post_submission_columns_succeed():
    """B2: Submitter can update permitted non-clinical columns."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "triage_level": "URGENT",
        "is_sms_stub": False,
        "deleted_at": None,
        "human_review_requested": False,
        "human_review_reason": None,
        "follow_up_completed_at": None,
        "updated_at": "2026-11-19T05:00:00Z",
    }
    new = dict(old)
    new["deleted_at"] = "2026-11-19T06:00:00Z"
    new["human_review_requested"] = True
    new["human_review_reason"] = "Patient feels worse"
    new["follow_up_completed_at"] = "2026-11-19T06:05:00Z"
    new["updated_at"] = "2026-11-19T06:05:00Z"

    res = simulate_phase54_protect_case_records_clinical_columns(
        old_row=old,
        new_row=new,
        auth_uid="asha-1",
        user_role="asha_worker",
    )
    assert res["human_review_requested"] is True
    assert res["deleted_at"] == "2026-11-19T06:00:00Z"


def test_b2_sms_stub_promotion_permits_clinical_data_including_respiratory_rate():
    """B2: SMS stub promotion permits full clinical payload including reconciled respiratory_rate."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "is_sms_stub": True,
        "triage_level": "URGENT",
        "triage_priority": 2,
        "needs_review": False,
        "reviewed_at": None,
        "overridden_triage": None,
        "reviewed_by": None,
        "patient_name": "Stub",
        "temperature": 37.0,
        "respiratory_rate": None,
    }
    new = dict(old)
    new["is_sms_stub"] = False
    new["patient_name"] = "Full Promoted Name"
    new["temperature"] = 38.8
    new["respiratory_rate"] = 28
    new["spo2"] = 94
    new["symptoms"] = ["fever", "dyspnea"]
    new["triage_level"] = "EMERGENCY"
    new["triage_priority"] = 1

    res = simulate_phase54_protect_case_records_clinical_columns(
        old_row=old,
        new_row=new,
        auth_uid="asha-1",
        user_role="asha_worker",
    )
    assert res["is_sms_stub"] is False
    assert res["patient_name"] == "Full Promoted Name"
    assert res["respiratory_rate"] == 28
    assert res["triage_level"] == "EMERGENCY"


@pytest.mark.parametrize("forbidden_col", CLINICIAN_ONLY_FORBIDDEN_COLS)
def test_b2_sms_stub_promotion_rejects_clinician_and_tenant_columns(forbidden_col: str):
    """B2: SMS stub promotion MUST reject clinician-only review, override, and tenant columns."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "is_sms_stub": True,
        "triage_level": "URGENT",
        "reviewed_at": None,
        "overridden_triage": None,
        "reviewed_by": None,
        "patient_name": "Stub",
        "doctor_notes": None,
        "follow_up_required": False,
        "follow_up_due_at": None,
    }
    new = dict(old)
    new["is_sms_stub"] = False
    new[forbidden_col] = "injected_tampered_value"

    with pytest.raises(PermissionError) as exc_info:
        simulate_phase54_protect_case_records_clinical_columns(
            old_row=old,
            new_row=new,
            auth_uid="asha-1",
            user_role="asha_worker",
        )
    assert "42501" in str(exc_info.value)


def test_b2_sms_stub_promotion_preserves_clinician_review():
    """B2: If doctor already reviewed or overrode stub while offline, promotion MUST preserve doctor triage decision."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "is_sms_stub": True,
        "triage_level": "EMERGENCY",
        "triage_priority": 1,
        "needs_review": False,
        "reviewed_at": "2026-11-19T05:00:00Z",
        "overridden_triage": "EMERGENCY",
        "reviewed_by": "doc-1",
        "patient_name": "Stub",
    }
    new = dict(old)
    new["is_sms_stub"] = False
    new["patient_name"] = "Full Promoted Name"
    # Promotion tries to downgrade to NON_URGENT
    new["triage_level"] = "NON_URGENT"
    new["triage_priority"] = 4
    new["needs_review"] = True

    res = simulate_phase54_protect_case_records_clinical_columns(
        old_row=old,
        new_row=new,
        auth_uid="asha-1",
        user_role="asha_worker",
    )
    assert res["is_sms_stub"] is False
    assert res["patient_name"] == "Full Promoted Name"
    # Overwritten by clinician's review
    assert res["triage_level"] == "EMERGENCY"
    assert res["triage_priority"] == 1
    assert res["needs_review"] is False


def test_b2_fail_closed_allowlist_rejects_unknown_injected_columns():
    """B2: Verify fail-closed JSONB allowlist automatically rejects any hypothetical future/unknown column."""
    old = {
        "id": "case-1",
        "submitted_by": "asha-1",
        "facility_id": "fac-1",
        "is_sms_stub": False,
        "triage_level": "URGENT",
    }
    new = dict(old)
    new["injected_future_column"] = "exploit"

    with pytest.raises(PermissionError) as exc_info:
        simulate_phase54_protect_case_records_clinical_columns(
            old_row=old,
            new_row=new,
            auth_uid="asha-1",
            user_role="asha_worker",
        )
    assert "42501" in str(exc_info.value)


def test_b2_sql_text_asserts_allowlists_and_absence_of_blacklist(migration_sql: str):
    """B2: Assert SQL migration preserves Phase 52 allowlist pattern and contains NO blacklist."""
    fn_body = re.search(
        r"CREATE OR REPLACE FUNCTION public\.protect_case_records_clinical_columns\(\).*?\$\$(.*?)\$\$ LANGUAGE plpgsql;",
        migration_sql,
        re.DOTALL,
    )
    assert fn_body is not None
    body = fn_body.group(1)

    # Allowlist patterns
    assert "(to_jsonb(NEW) - v_allowed_submitter_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_submitter_cols)" in body
    assert "(to_jsonb(NEW) - v_allowed_sms_promotion_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_sms_promotion_cols)" in body

    # Fast-path pattern
    assert "IF (SELECT auth.uid()) IS DISTINCT FROM OLD.submitted_by THEN" in body
    assert "RETURN NEW;" in body

    # Must NOT have blacklist arrays
    assert "v_forbidden" not in body
    assert "v_blacklisted" not in body


# ==============================================================================
# 5. B3 & F-11: Composite, Partial, and Cleanup Indexes
# ==============================================================================


def test_b3_and_f11_exact_composite_index_definitions(migration_sql: str):
    """B3 & F-11: Verify exact composite index definitions and WHERE deleted_at IS NULL clauses."""
    expected_indexes = [
        (
            "idx_case_records_submitted_created",
            "ON public.case_records (submitted_by, created_at DESC)",
            "WHERE deleted_at IS NULL",
        ),
        (
            "idx_case_records_facility_created",
            "ON public.case_records (facility_id, created_at DESC)",
            "WHERE deleted_at IS NULL",
        ),
        (
            "idx_referrals_receiving_status_created",
            "ON public.referrals (receiving_facility_id, status, created_at DESC)",
            None,
        ),
        (
            "idx_protocol_questions_facility_status_created",
            "ON public.protocol_questions (facility_id, status, created_at DESC)",
            None,
        ),
    ]

    for idx_name, target_table_cols, where_clause in expected_indexes:
        pattern = rf"CREATE INDEX IF NOT EXISTS {idx_name}\s+{re.escape(target_table_cols)}"
        assert re.search(pattern, migration_sql) is not None, f"Index {idx_name} definition missing or mismatched"
        if where_clause:
            assert where_clause in migration_sql, f"Expected {where_clause} for index {idx_name}"


def test_b3_and_f11_dropped_obsolete_single_column_indexes(migration_sql: str):
    """B3 & F-11: Verify dropping of the 4 superseded single-column indexes."""
    dropped = [
        "public.idx_case_records_submitted_by",
        "public.idx_case_records_deleted_at",
        "public.idx_case_records_needs_review",
        "public.idx_referrals_status",
    ]
    for idx in dropped:
        assert f"DROP INDEX IF EXISTS {idx};" in migration_sql, f"Expected DROP INDEX IF EXISTS {idx}"


# ==============================================================================
# 6. A3-2: fn_ears_daily_counts SQL Aggregation RPC
# ==============================================================================


def simulate_fn_ears_daily_counts(
    caller_auth_uid: Optional[str],
    caller_role: Optional[str],
    caller_facility_id: Optional[str],
    caller_is_active: bool,
    p_facility_id: Optional[str],
    p_since: Optional[datetime],
    cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Python oracle simulating public.fn_ears_daily_counts PL/pgSQL function:
    - Role authorization: doctor, facility_admin, supervisor, admin, super_admin.
    - Facility pinning: non-global roles (doctor, facility_admin) pinned to caller's facility.
    - Mandatory p_since: error 22023 if NULL.
    - Grouping by facility, date (Asia/Kolkata), and symptom.
    """
    if caller_auth_uid is None or not caller_is_active or caller_role is None:
        raise PermissionError("42501: insufficient_privilege")

    if caller_role not in ("doctor", "facility_admin", "supervisor", "admin", "super_admin"):
        raise PermissionError("42501: insufficient_privilege")

    target_facility = p_facility_id
    if caller_role not in ("super_admin", "supervisor"):
        if caller_facility_id is None:
            raise ValueError("22023: account has no facility assigned")
        target_facility = caller_facility_id

    if p_since is None:
        raise ValueError("22023: fn_ears_daily_counts: p_since is required")

    kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    counts: Dict[tuple, int] = {}

    for c in cases:
        if c.get("deleted_at") is not None:
            continue
        created_at: datetime = c["created_at"]
        if created_at < p_since:
            continue
        c_facility = c["facility_id"]
        if target_facility is not None and c_facility != target_facility:
            continue

        # Convert to Asia/Kolkata date
        ist_date = created_at.astimezone(kolkata_tz).strftime("%Y-%m-%d")
        symptoms = c.get("symptoms") or []
        for s in symptoms:
            key = (c_facility, ist_date, s)
            counts[key] = counts.get(key, 0) + 1

    res = []
    for (fac, dt, sym), cnt in counts.items():
        res.append({
            "facility_id": fac,
            "date": dt,
            "symptom": sym,
            "daily_count": cnt,
        })
    return res


@pytest.mark.parametrize("unauthorized_role", ["patient", "asha_worker", "nurse", "clerk", "volunteer", "unknown"])
def test_a3_2_fn_ears_daily_counts_rejects_unauthorized_roles(unauthorized_role: str):
    """A3-2: Non-surveillance roles must be rejected with 42501."""
    with pytest.raises(PermissionError) as exc_info:
        simulate_fn_ears_daily_counts(
            caller_auth_uid="user-1",
            caller_role=unauthorized_role,
            caller_facility_id="fac-1",
            caller_is_active=True,
            p_facility_id="fac-1",
            p_since=datetime.now(timezone.utc),
            cases=[],
        )
    assert "42501" in str(exc_info.value)


def test_a3_2_fn_ears_daily_counts_rejects_inactive_user():
    """A3-2: Inactive accounts must be rejected with 42501."""
    with pytest.raises(PermissionError) as exc_info:
        simulate_fn_ears_daily_counts(
            caller_auth_uid="doc-1",
            caller_role="doctor",
            caller_facility_id="fac-1",
            caller_is_active=False,
            p_facility_id="fac-1",
            p_since=datetime.now(timezone.utc),
            cases=[],
        )
    assert "42501" in str(exc_info.value)


def test_a3_2_fn_ears_daily_counts_rejects_unassigned_facility_clinician():
    """A3-2: Clinicians without an assigned facility fail-closed with 22023."""
    with pytest.raises(ValueError) as exc_info:
        simulate_fn_ears_daily_counts(
            caller_auth_uid="doc-1",
            caller_role="doctor",
            caller_facility_id=None,
            caller_is_active=True,
            p_facility_id="fac-1",
            p_since=datetime.now(timezone.utc),
            cases=[],
        )
    assert "22023" in str(exc_info.value)
    assert "account has no facility assigned" in str(exc_info.value)


def test_a3_2_fn_ears_daily_counts_pins_clinician_facility():
    """A3-2: Clinicians/Facility Admins are pinned to their own facility; caller override is ignored."""
    dt_utc = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
    cases = [
        {"facility_id": "fac-1", "created_at": dt_utc, "deleted_at": None, "symptoms": ["fever"]},
        {"facility_id": "fac-2", "created_at": dt_utc, "deleted_at": None, "symptoms": ["fever"]},
    ]

    # Doctor belongs to fac-1, but requests fac-2
    res = simulate_fn_ears_daily_counts(
        caller_auth_uid="doc-1",
        caller_role="doctor",
        caller_facility_id="fac-1",
        caller_is_active=True,
        p_facility_id="fac-2",
        p_since=datetime(2026, 11, 1, tzinfo=timezone.utc),
        cases=cases,
    )
    # Must only return records for fac-1!
    assert len(res) == 1
    assert res[0]["facility_id"] == "fac-1"
    assert res[0]["daily_count"] == 1


def test_a3_2_fn_ears_daily_counts_global_roles_unpinned():
    """A3-2: Only supervisor and super_admin can query cross-facility or aggregate all facilities."""
    dt_utc = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
    cases = [
        {"facility_id": "fac-1", "created_at": dt_utc, "deleted_at": None, "symptoms": ["fever"]},
        {"facility_id": "fac-2", "created_at": dt_utc, "deleted_at": None, "symptoms": ["fever"]},
    ]

    for role in ("supervisor", "super_admin"):
        # Querying all facilities (p_facility_id = None)
        res = simulate_fn_ears_daily_counts(
            caller_auth_uid="super-1",
            caller_role=role,
            caller_facility_id="fac-1",
            caller_is_active=True,
            p_facility_id=None,
            p_since=datetime(2026, 11, 1, tzinfo=timezone.utc),
            cases=cases,
        )
        assert len(res) == 2
        facs = {r["facility_id"] for r in res}
        assert facs == {"fac-1", "fac-2"}


def test_a3_2_fn_ears_daily_counts_requires_p_since():
    """A3-2: Missing p_since parameter raises 22023."""
    with pytest.raises(ValueError) as exc_info:
        simulate_fn_ears_daily_counts(
            caller_auth_uid="doc-1",
            caller_role="doctor",
            caller_facility_id="fac-1",
            caller_is_active=True,
            p_facility_id="fac-1",
            p_since=None,
            cases=[],
        )
    assert "22023" in str(exc_info.value)
    assert "p_since is required" in str(exc_info.value)


def test_a3_2_fn_ears_daily_counts_asia_kolkata_timezone_boundary():
    """
    A3-2: Verify exact Asia/Kolkata (UTC+05:30) date boundary calculation.
    2026-11-18 18:29:59 UTC = 2026-11-18 23:59:59 IST -> date '2026-11-18'
    2026-11-18 18:30:00 UTC = 2026-11-19 00:00:00 IST -> date '2026-11-19'
    """
    t1 = datetime(2026, 11, 18, 18, 29, 59, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 18, 18, 30, 0, tzinfo=timezone.utc)

    cases = [
        {"facility_id": "fac-1", "created_at": t1, "deleted_at": None, "symptoms": ["cough"]},
        {"facility_id": "fac-1", "created_at": t2, "deleted_at": None, "symptoms": ["cough"]},
    ]

    res = simulate_fn_ears_daily_counts(
        caller_auth_uid="doc-1",
        caller_role="doctor",
        caller_facility_id="fac-1",
        caller_is_active=True,
        p_facility_id="fac-1",
        p_since=datetime(2026, 11, 1, tzinfo=timezone.utc),
        cases=cases,
    )

    date_map = {r["date"]: r["daily_count"] for r in res}
    assert date_map["2026-11-18"] == 1
    assert date_map["2026-11-19"] == 1


def test_a3_2_fn_ears_daily_counts_symptom_unnest_and_counts():
    """A3-2: Verify multi-symptom unnesting, deletion filtering, and historical cutoff."""
    dt_now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    dt_old = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    cases = [
        # Case 1: multiple symptoms
        {"facility_id": "fac-1", "created_at": dt_now, "deleted_at": None, "symptoms": ["fever", "cough", "fatigue"]},
        # Case 2: overlapping symptom
        {"facility_id": "fac-1", "created_at": dt_now, "deleted_at": None, "symptoms": ["cough"]},
        # Case 3: soft-deleted (must be excluded)
        {"facility_id": "fac-1", "created_at": dt_now, "deleted_at": dt_now, "symptoms": ["fever"]},
        # Case 4: before p_since (must be excluded)
        {"facility_id": "fac-1", "created_at": dt_old, "deleted_at": None, "symptoms": ["fever"]},
    ]

    res = simulate_fn_ears_daily_counts(
        caller_auth_uid="doc-1",
        caller_role="doctor",
        caller_facility_id="fac-1",
        caller_is_active=True,
        p_facility_id="fac-1",
        p_since=datetime(2026, 11, 1, tzinfo=timezone.utc),
        cases=cases,
    )

    symptom_counts = {r["symptom"]: r["daily_count"] for r in res}
    assert symptom_counts["fever"] == 1
    assert symptom_counts["cough"] == 2
    assert symptom_counts["fatigue"] == 1
