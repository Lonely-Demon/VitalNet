"""
Regression and security hardening test suite for VitalNet Phase 53 (VN-53-01 through VN-53-12).

Covers:
- VN-53-01: Inbound SMS gateway mandatory authentication (HTTP 401 when missing/invalid).
- VN-53-02: Inbound SMS gateway caller facility pinning to authenticated user's resolved_facility_id.
- VN-53-03: Clinician /api/cases queue fail-closed with HTTP 400 when facility is unassigned.
- VN-53-04: Supervisor role denied clinical case access (followups due, DSR export, DSR erase).
- VN-53-05: Constant-time comparison for escalation scheduler token (secrets.compare_digest).
- VN-53-06: case_records_update_policy facility pinning even when reviewed_by IS NULL.
- VN-53-07: Consent revocation supervisor denial.
- VN-53-08: fn_deterioration_count window ceiling (max 30 days) and role check.
- VN-53-09: Metrics RPCs two-tier alignment and null facility fail-closed guards.
- VN-53-10: profiles_insert_own self-registration RLS policy.
- VN-53-11: fn_rate_limit fixed 4-hour cleanup horizon.
- VN-53-12: Ancillary tables two-tier facility scoping and is_active check.
"""
import asyncio
from pathlib import Path
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
try:
    import sqlparse
except ImportError:
    sqlparse = None
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes import cases, push_routes
from app.api.routes.dsr_routes import _authorize_dsr_access

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "supabase"
    / "migrations"
    / "phase53_security_hardening.sql"
)


@pytest.fixture(scope="module")
def phase53_sql():
    assert MIGRATION_PATH.exists(), f"Phase 53 migration file not found at {MIGRATION_PATH}"
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        return f.read()


def make_request(headers=None, body_json=None):
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))
    if body_json is not None:
        raw_headers.append((b"content-type", b"application/json"))

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/cases/sms-gateway",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    if body_json is not None:
        req.json = AsyncMock(return_value=body_json)
    return req


# ── VN-53-01: Inbound SMS Gateway Mandatory Auth ──────────────────────────────


def test_vn53_01_sms_gateway_rejects_unauthenticated():
    """Unauthenticated SMS requests without bearer or webhook token must fail with HTTP 401."""
    async def _test():
        req = make_request(body_json={"body": "TRIAGE 30 F chest_pain"})
        with pytest.raises(HTTPException) as exc_info:
            await cases.ingest_sms_gateway(request=req, authorization=None)
        assert exc_info.value.status_code == 401
        assert "Authorization" in exc_info.value.detail or "Authentication required" in exc_info.value.detail

    asyncio.run(_test())


def test_vn53_01_sms_gateway_rejects_invalid_bearer_token():
    """SMS requests with malformed or invalid bearer tokens must fail with HTTP 401."""
    async def _test():
        req = make_request(headers={"Authorization": "Bearer bad-token"}, body_json={"body": "TRIAGE 30 F chest_pain"})
        with patch("app.api.routes.cases.extract_bearer_token", return_value="bad-token"), \
             patch("app.api.routes.cases._verify_token", side_effect=Exception("Invalid signature")):
            with pytest.raises(HTTPException) as exc_info:
                await cases.ingest_sms_gateway(request=req, authorization="Bearer bad-token")
            assert exc_info.value.status_code == 401

    asyncio.run(_test())


def test_vn53_01_sms_gateway_rejects_disallowed_role():
    """Authenticated users with unauthorized roles (e.g. supervisor) must receive HTTP 403."""
    async def _test():
        req = make_request(headers={"Authorization": "Bearer sup-token"}, body_json={"body": "TRIAGE 30 F chest_pain"})
        with patch("app.api.routes.cases.extract_bearer_token", return_value="sup-token"), \
             patch("app.api.routes.cases._verify_token", return_value={"sub": "sup-user-id"}), \
             patch("app.api.routes.cases._resolve_profile", return_value=(True, "supervisor", "fac-1")):
            with pytest.raises(HTTPException) as exc_info:
                await cases.ingest_sms_gateway(request=req, authorization="Bearer sup-token")
            assert exc_info.value.status_code == 403
            assert "Role 'supervisor' is not permitted" in exc_info.value.detail

    asyncio.run(_test())


# ── VN-53-02: SMS Caller Facility Pinning ────────────────────────────────────


def test_vn53_02_sms_gateway_pins_facility_to_clinician_profile():
    """Authenticated clinician cannot inject a custom facility_id in request body; must pin to profile."""
    async def _test():
        mock_inserted = []
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.upsert.side_effect = lambda payload, **kw: mock_inserted.append(payload) or mock_query
        mock_query.execute.return_value = MagicMock(data=[{"id": "case-1"}])
        mock_db.table.return_value = mock_query

        clinician_facility = "11111111-2222-3333-4444-555555555555"
        injected_facility = "99999999-9999-9999-9999-999999999999"

        req = make_request(
            headers={"Authorization": "Bearer doc-token"},
            body_json={
                "body": "TRIAGE 45 M chest_pain,breathlessness",
                "facility_id": injected_facility,
            },
        )

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="doc-token"), \
             patch("app.api.routes.cases._verify_token", return_value={"sub": "doc-user-id"}), \
             patch("app.api.routes.cases._resolve_profile", return_value=(True, "doctor", clinician_facility)):

            res = await cases.ingest_sms_gateway(request=req, authorization="Bearer doc-token")
            assert res["status"] == "queued"
            assert len(mock_inserted) == 1
            stub = mock_inserted[0]
            # Must strictly pin to doctor's assigned facility, completely ignoring injected facility
            assert stub["facility_id"] == clinician_facility

    asyncio.run(_test())


def test_vn53_02_sms_gateway_allows_super_admin_custom_facility():
    """Super admin is permitted to explicitly specify facility_id for SMS ingestion."""
    async def _test():
        mock_inserted = []
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.upsert.side_effect = lambda payload, **kw: mock_inserted.append(payload) or mock_query
        mock_query.execute.return_value = MagicMock(data=[{"id": "case-1"}])
        mock_db.table.return_value = mock_query

        target_facility = "88888888-8888-8888-8888-888888888888"

        req = make_request(
            headers={"Authorization": "Bearer sa-token"},
            body_json={
                "body": "TRIAGE 45 M chest_pain,breathlessness",
                "facility_id": target_facility,
            },
        )

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="sa-token"), \
             patch("app.api.routes.cases._verify_token", return_value={"sub": "sa-user-id"}), \
             patch("app.api.routes.cases._resolve_profile", return_value=(True, "super_admin", None)):

            res = await cases.ingest_sms_gateway(request=req, authorization="Bearer sa-token")
            assert res["status"] == "queued"
            assert len(mock_inserted) == 1
            stub = mock_inserted[0]
            assert stub["facility_id"] == target_facility

    asyncio.run(_test())


# ── VN-53-03: Clinician Facility Fail-Closed ─────────────────────────────────


def test_vn53_03_doctor_without_facility_fails_closed_with_400():
    """A doctor account with no facility_id must fail closed with HTTP 400 on /api/cases."""
    async def _test():
        req = make_request()
        user_payload = {"sub": "doc-no-fac", "role": "doctor"}

        with patch("app.api.routes.cases.extract_bearer_token", return_value="token"), \
             patch("app.api.routes.cases.get_supabase_for_user"), \
             patch("app.api.routes.cases._resolved_role", return_value="doctor"), \
             patch("app.api.routes.cases._resolved_facility", return_value=None):

            with pytest.raises(HTTPException) as exc_info:
                await cases.get_cases(
                    request=req,
                    authorization="Bearer token",
                    user=user_payload,
                )
            assert exc_info.value.status_code == 400
            assert "Account has no facility assigned" in exc_info.value.detail

    asyncio.run(_test())


# ── VN-53-04: Supervisor PHI & DSR Exclusion ─────────────────────────────────


def test_vn53_04_supervisor_denied_followups_due():
    """Supervisor role is denied access to /api/cases/followups/due (HTTP 403)."""
    from app.core.auth import require_role
    role_guard = require_role("asha_worker", "doctor", "admin", "super_admin")

    async def _test():
        sup_user = {"sub": "sup-1", "resolved_role": "supervisor"}
        with pytest.raises(HTTPException) as exc_info:
            await role_guard(user=sup_user)
        assert exc_info.value.status_code == 403

    asyncio.run(_test())


def test_vn53_04_supervisor_denied_dsr_access():
    """_authorize_dsr_access must raise HTTP 403 when invoked with supervisor role."""
    user = {"sub": "sup-1", "resolved_role": "supervisor"}
    case = {"id": "case-1", "facility_id": "fac-1"}

    with pytest.raises(HTTPException) as exc_info:
        _authorize_dsr_access(user, case)
    assert exc_info.value.status_code == 403
    assert "Supervisors are not permitted" in exc_info.value.detail


def test_vn53_04_dsr_access_facility_boundary_for_phc_admin():
    """PHC admin is strictly forbidden from accessing DSR cases outside their own facility."""
    admin_user = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}
    diff_case = {"id": "case-2", "facility_id": "fac-2"}

    with pytest.raises(HTTPException) as exc_info:
        _authorize_dsr_access(admin_user, diff_case)
    assert exc_info.value.status_code == 403
    assert "outside your assigned facility" in exc_info.value.detail


# ── VN-53-05: Constant-Time Comparison on Scheduler Token ────────────────────


def test_vn53_05_constant_time_comparison_enforced(monkeypatch):
    """push_routes.check_emergency_escalations uses secrets.compare_digest for token verification."""
    mock_compare = MagicMock(return_value=True)
    monkeypatch.setattr("app.api.routes.push_routes.secrets.compare_digest", mock_compare)
    monkeypatch.setattr("app.api.routes.push_routes.settings.internal_scheduler_token", "secret-token-xyz")

    async def _test():
        req = make_request()
        user = {"sub": "adm-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.is_.return_value.lt.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        monkeypatch.setattr("app.api.routes.push_routes.supabase_admin", mock_db)

        res = await push_routes.check_emergency_escalations(
            request=req,
            authorization="Bearer token",
            x_internal_scheduler_token="secret-token-xyz",
            user=user,
        )
        assert res["checked"] == 0
        mock_compare.assert_called_once_with("secret-token-xyz", "secret-token-xyz")

    asyncio.run(_test())


# ── VN-53-06: Database Migration case_records_update_policy ──────────────────


def test_vn53_06_case_records_update_policy_no_reviewed_by_null_bypass(phase53_sql):
    """Ensure case_records_update_policy has removed reviewed_by IS NULL short-circuit."""
    # Check for policy definition
    match = re.search(
        r"CREATE POLICY case_records_update_policy ON public\.case_records\s+FOR UPDATE TO authenticated\s+USING \((.*?)\)\s+WITH CHECK \((.*?)\);",
        phase53_sql,
        re.DOTALL,
    )
    assert match is not None, "case_records_update_policy must be defined with USING and WITH CHECK"
    with_check_clause = match.group(2)

    assert "reviewed_by IS NULL" not in with_check_clause, (
        "case_records_update_policy WITH CHECK in phase53 must not short-circuit on reviewed_by IS NULL"
    )
    assert "p.facility_id = case_records.facility_id" in with_check_clause
    assert "p.role = 'super_admin'::text" in with_check_clause
    assert "p.is_active = true" in with_check_clause


# ── VN-53-07: Consent Revocation Supervisor Denial ───────────────────────────


def test_vn53_07_fn_erase_case_pii_explicit_supervisor_denial(phase53_sql):
    """Ensure fn_erase_case_pii explicitly denies supervisor role with 42501."""
    assert "IF v_role = 'supervisor' THEN" in phase53_sql
    assert "RAISE EXCEPTION 'insufficient_privilege" in phase53_sql


# ── VN-53-08: fn_deterioration_count Window & Role Checks ────────────────────


def test_vn53_08_fn_deterioration_count_guards(phase53_sql):
    """Ensure fn_deterioration_count enforces 30-day window ceiling and role whitelist."""
    # Window ceiling
    assert "p_window_days > 30" in phase53_sql
    assert "fn_deterioration_count: p_window_days must be between 1 and 30" in phase53_sql

    # Role checks
    match = re.search(
        r"v_role NOT IN \((.*?)\)",
        phase53_sql,
    )
    assert match is not None
    roles = match.group(1)
    for expected in ["'asha_worker'", "'doctor'", "'facility_admin'", "'admin'", "'super_admin'"]:
        assert expected in roles
    assert "'supervisor'" not in roles


# ── VN-53-09: Metrics RPCs Two-Tier Alignment ────────────────────────────────


def test_vn53_09_metrics_rpcs_two_tier_and_null_facility_guards(phase53_sql):
    """Ensure fn_team_metrics, fn_outbreak_signal_counts, and fn_triage_metrics enforce two-tier guards."""
    # fn_team_metrics & fn_outbreak_signal_counts: non-global roles require v_own_facility while preserving supervisor global aggregate scope
    assert "IF v_role NOT IN ('super_admin', 'supervisor') THEN" in phase53_sql
    assert "account has no facility assigned" in phase53_sql

    # fn_triage_metrics: admin requires non-null facility
    triage_metrics_match = re.search(
        r"CREATE OR REPLACE FUNCTION public\.fn_triage_metrics\(\).*?\$\$(.*?)\$\$",
        phase53_sql,
        re.DOTALL,
    )
    assert triage_metrics_match is not None
    body = triage_metrics_match.group(1)
    assert "IF v_own_facility IS NULL THEN" in body
    assert "RAISE EXCEPTION 'account has no facility assigned'" in body


# ── VN-53-10: profiles_insert_own RLS Policy ─────────────────────────────────


def test_vn53_10_profiles_insert_own_rls_policy(phase53_sql):
    """Ensure profiles_insert_own restricts self-registration to non-privileged inactive roles."""
    match = re.search(
        r"CREATE POLICY profiles_insert_own ON public\.profiles\s+FOR INSERT TO authenticated\s+WITH CHECK \((.*?)\);",
        phase53_sql,
        re.DOTALL,
    )
    assert match is not None, "profiles_insert_own policy missing in phase53_security_hardening.sql"
    check_body = match.group(1)
    assert "id = auth.uid()" in check_body
    assert "ARRAY['asha_worker'::text, 'doctor'::text]" in check_body
    assert "is_active = false" in check_body


# ── VN-53-11: fn_rate_limit 4-Hour Horizon ───────────────────────────────────


def test_vn53_11_fn_rate_limit_cleanup_horizon(phase53_sql):
    """Ensure fn_rate_limit uses a fixed 4-hour cleanup horizon."""
    rate_limit_match = re.search(
        r"CREATE OR REPLACE FUNCTION public\.fn_rate_limit\(.*?\)\s+RETURNS boolean.*?\$\$(.*?)\$\$",
        phase53_sql,
        re.DOTALL,
    )
    assert rate_limit_match is not None
    body = rate_limit_match.group(1)
    assert "now() - interval '4 hours'" in body
    assert "make_interval(secs => p_window_s * 4)" not in body


# ── VN-53-12: Ancillary Tables Two-Tier & is_active ──────────────────────────


def test_vn53_12_ancillary_tables_scoping_and_active_guards(phase53_sql):
    """Ensure case_outcomes, case_reviews, case_attachments, client_events, referrals, and audit log have two-tier guards."""
    for table in ["case_outcomes", "case_reviews", "case_attachments", "client_events", "referrals"]:
        assert f"ON public.{table}" in phase53_sql, f"Missing policies for table {table}"

    # Verify is_active = true is present in all policies on ancillary tables
    assert phase53_sql.count("p.is_active = true") >= 8

    # Verify phi_audit_log insert policy
    assert "CREATE POLICY phi_audit_log_insert_authenticated ON public.phi_audit_log" in phase53_sql
    assert "user_id = auth.uid()" in phase53_sql


def test_migration_sqlparse_tokenization(phase53_sql):
    """Ensure the entire migration parses cleanly into SQL statements without syntax breaks."""
    if sqlparse is not None:
        statements = sqlparse.split(phase53_sql)
        assert len(statements) >= 12
        for s in statements:
            if s.strip():
                parsed = sqlparse.parse(s)[0]
                tokens = [t for t in parsed.tokens if not t.is_whitespace]
                assert len(tokens) > 0
    else:
        statements = [s.strip() for s in phase53_sql.split(";") if s.strip()]
        assert len(statements) >= 12
