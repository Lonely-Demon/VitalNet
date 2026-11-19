"""
backend/tests/test_phase54_scale_hardening.py
Verification suite for Phase 54 Performance, Indexing & Scale Hardening migration and server invariants:
- F-05: respiratory_rate column reconciliation & bounds constraint [5, 120]
- B1: STABLE RLS helpers and InitPlan caching for asha_select_own
- B2: Fast-path short-circuit in protect_case_records_clinical_columns() with preserved JSONB allowlist
- B3 & F-11: 4 composite/partial indexes created, 4 obsolete single-column indexes dropped
- A3-2: fn_ears_daily_counts SQL aggregation RPC with IST timezone grouping
- F-06: Async streaming CSV export in analytics_routes.py
"""

from pathlib import Path
import re
import pytest

try:
    import sqlparse
except ImportError:
    sqlparse = None


@pytest.fixture
def phase54_sql() -> str:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "supabase"
        / "migrations"
        / "phase54_performance_indexing_and_scale_hardening.sql"
    )
    assert migration_path.exists(), f"Migration file missing at {migration_path}"
    return migration_path.read_text(encoding="utf-8")


def test_phase54_migration_transaction_and_idempotency(phase54_sql: str):
    """Ensure the migration is enclosed in BEGIN; ... COMMIT; and parses cleanly."""
    assert "BEGIN;" in phase54_sql, "Migration must contain BEGIN;"
    assert phase54_sql.strip().endswith("COMMIT;"), "Migration must end with COMMIT;"

    if sqlparse is not None:
        statements = sqlparse.split(phase54_sql)
        assert len(statements) >= 8
        for s in statements:
            if s.strip():
                parsed = sqlparse.parse(s)[0]
                tokens = [t for t in parsed.tokens if not t.is_whitespace]
                assert len(tokens) > 0


def test_f05_respiratory_rate_schema_reconciliation(phase54_sql: str):
    """F-05: Verify respiratory_rate column and bounds constraint [5, 120]."""
    assert "ADD COLUMN IF NOT EXISTS respiratory_rate integer" in phase54_sql
    assert "case_records_respiratory_rate_bounds" in phase54_sql
    assert "CHECK (respiratory_rate IS NULL OR (respiratory_rate >= 5 AND respiratory_rate <= 120))" in phase54_sql


def test_b1_stable_rls_helpers_and_asha_select_own(phase54_sql: str):
    """B1: Verify STABLE RLS helpers and InitPlan caching in asha_select_own."""
    for fn in ["get_user_role", "get_user_facility", "get_current_user_role", "get_current_user_facility"]:
        pattern = rf"CREATE OR REPLACE FUNCTION public\.{fn}\b.*?LANGUAGE sql\s+STABLE\s+SECURITY DEFINER"
        assert re.search(pattern, phase54_sql, re.DOTALL) is not None, f"Function {fn} must be STABLE SECURITY DEFINER"

    # Verify grants
    assert "GRANT EXECUTE ON FUNCTION public.get_current_user_role() TO authenticated;" in phase54_sql
    assert "GRANT EXECUTE ON FUNCTION public.get_current_user_facility() TO authenticated;" in phase54_sql

    # Verify policy asha_select_own uses (SELECT auth.uid()) and get_current_user_role/facility
    policy_match = re.search(r"CREATE POLICY asha_select_own ON public\.case_records\s+FOR SELECT TO authenticated\s+USING \((.*?)\);", phase54_sql, re.DOTALL)
    assert policy_match is not None, "Policy asha_select_own not found"
    body = policy_match.group(1)
    assert "(SELECT auth.uid()) IS NOT NULL" in body
    assert "submitted_by = (SELECT auth.uid())" in body
    assert "(SELECT public.get_current_user_role()) = 'super_admin'" in body
    assert "(SELECT public.get_current_user_facility()) = case_records.facility_id" in body


def test_b2_fast_path_short_circuit_with_preserved_allowlist(phase54_sql: str):
    """B2: Verify fast-path short-circuit while strictly preserving Phase 52's fail-closed JSONB allowlist."""
    fn_match = re.search(
        r"CREATE OR REPLACE FUNCTION public\.protect_case_records_clinical_columns\(\).*?\$\$(.*?)\$\$ LANGUAGE plpgsql;",
        phase54_sql,
        re.DOTALL,
    )
    assert fn_match is not None, "protect_case_records_clinical_columns not found"
    body = fn_match.group(1)

    # Fast-path check
    assert "IF (SELECT auth.uid()) IS DISTINCT FROM OLD.submitted_by THEN" in body
    assert "RETURN NEW;" in body

    # STRICT SAFETY INVARIANT: Fail-closed JSONB allowlist must be preserved; column blacklist prohibited
    assert "v_allowed_submitter_cols text[] :=" in body
    assert "v_allowed_sms_promotion_cols text[] :=" in body
    assert "(to_jsonb(NEW) - v_allowed_submitter_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_submitter_cols)" in body
    assert "(to_jsonb(NEW) - v_allowed_sms_promotion_cols) IS DISTINCT FROM (to_jsonb(OLD) - v_allowed_sms_promotion_cols)" in body
    assert "RAISE EXCEPTION 'Clinical, triage, override, and identity columns cannot be modified by the submitter'" in body


def test_b3_and_f11_composite_and_cleanup_indexes(phase54_sql: str):
    """B3 & F-11: Verify 4 composite partial indexes and dropping obsolete single-column indexes."""
    # Composite indexes
    assert "CREATE INDEX IF NOT EXISTS idx_case_records_submitted_created" in phase54_sql
    assert "ON public.case_records (submitted_by, created_at DESC)" in phase54_sql
    assert "WHERE deleted_at IS NULL;" in phase54_sql

    assert "CREATE INDEX IF NOT EXISTS idx_case_records_facility_created" in phase54_sql
    assert "ON public.case_records (facility_id, created_at DESC)" in phase54_sql

    assert "CREATE INDEX IF NOT EXISTS idx_referrals_receiving_status_created" in phase54_sql
    assert "ON public.referrals (receiving_facility_id, status, created_at DESC);" in phase54_sql

    assert "CREATE INDEX IF NOT EXISTS idx_protocol_questions_facility_status_created" in phase54_sql
    assert "ON public.protocol_questions (facility_id, status, created_at DESC);" in phase54_sql

    # Dropped indexes
    assert "DROP INDEX IF EXISTS public.idx_case_records_submitted_by;" in phase54_sql
    assert "DROP INDEX IF EXISTS public.idx_case_records_deleted_at;" in phase54_sql
    assert "DROP INDEX IF EXISTS public.idx_case_records_needs_review;" in phase54_sql
    assert "DROP INDEX IF EXISTS public.idx_referrals_status;" in phase54_sql


def test_a3_2_fn_ears_daily_counts_rpc(phase54_sql: str):
    """A3-2: Verify fn_ears_daily_counts SQL aggregation RPC with IST timezone."""
    fn_match = re.search(
        r"CREATE OR REPLACE FUNCTION public\.fn_ears_daily_counts\(.*?\)\s+RETURNS TABLE\((.*?)\)\s+LANGUAGE plpgsql\s+SECURITY DEFINER\s+SET search_path = public\s+AS \$\$(.*?)\$\$;",
        phase54_sql,
        re.DOTALL,
    )
    assert fn_match is not None, "fn_ears_daily_counts not found"
    returns_table = fn_match.group(1)
    body = fn_match.group(2)

    assert "facility_id uuid" in returns_table
    assert "date text" in returns_table
    assert "symptom text" in returns_table
    assert "daily_count bigint" in returns_table

    # Role check
    assert "'doctor', 'facility_admin', 'supervisor', 'admin', 'super_admin'" in body
    # Tenancy check
    assert "p_facility_id := v_own_facility;" in body
    assert "fn_ears_daily_counts: p_since is required" in body

    # IST timezone and symptom unnest
    assert "to_char(cr.created_at AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD') AS date" in body
    assert "jsonb_array_elements_text(to_jsonb(cr.symptoms)) AS s(symptom)" in body
    assert "COUNT(*)::bigint AS daily_count" in body

    # Grants
    assert "REVOKE ALL ON FUNCTION public.fn_ears_daily_counts(uuid, timestamptz) FROM PUBLIC;" in phase54_sql
    assert "GRANT EXECUTE ON FUNCTION public.fn_ears_daily_counts(uuid, timestamptz) TO authenticated;" in phase54_sql


def test_f06_analytics_export_async_generator_streaming():
    """F-06: Verify export_cases uses an asynchronous generator streaming chunks to StreamingResponse."""
    import asyncio
    import inspect
    from unittest.mock import MagicMock, patch
    from starlette.requests import Request
    from app.api.routes import analytics_routes

    async def _run():
        def make_dummy_request(method="GET", path="/api/analytics/cases/export"):
            scope = {
                "type": "http",
                "http_version": "1.1",
                "method": method,
                "path": path,
                "raw_path": path.encode("ascii"),
                "query_string": b"date_from=2026-01-01&date_to=2026-01-02",
                "headers": [(b"host", b"testserver")],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
                "scheme": "http",
            }
            return Request(scope)

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.is_.return_value = mock_query
        mock_query.gte.return_value = mock_query
        mock_query.lte.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value = mock_query

        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"
        user_context = {"sub": "admin-1", "resolved_role": "super_admin", "resolved_facility_id": None}

        with patch("app.api.routes.analytics_routes.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.analytics_routes.log_phi_access"):

            req = make_dummy_request()
            streaming_resp = await analytics_routes.export_cases(
                request=req,
                date_from="2026-01-01",
                date_to="2026-01-02",
                authorization=f"Bearer {fake_token}",
                user=user_context,
            )

            # Must return StreamingResponse with an asynchronous generator body_iterator
            assert inspect.isasyncgen(streaming_resp.body_iterator), "body_iterator must be an async generator"

            chunks = []
            async for chunk in streaming_resp.body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))

            body = "".join(chunks)
            # Verify CSV header is emitted
            assert "id" in body
            assert "created_at" in body
            assert "triage_level" in body

    asyncio.run(_run())

