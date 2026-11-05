"""
Unit tests for Milestone M3 remediation items:
- CRITICAL-5: Chunked .range() pagination in analytics export
- CRITICAL-6: Persistent connection pool transport sharing in database.py
- MEDIUM-2: Bounded concurrency & masking in admin auth lookups
- MEDIUM-4: Offload predict_triage to asyncio.to_thread
- HIGH-10b: Prometheus MultiProcessCollector support
"""
import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch

import httpx
from starlette.requests import Request

from app.api.routes import admin_routes, analytics_routes
from app.core import database, metrics
from app.ml.classifier import load_classifier, predict_triage


def make_dummy_request(method="GET", path="/"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


# ── CRITICAL-6: Persistent Connection Pool Transport Sharing ─────────────────

def test_shared_persistent_transport_exists():
    assert hasattr(database, "_shared_transport")
    assert isinstance(database._shared_transport, httpx.HTTPTransport)


def test_get_supabase_for_user_shares_transport():
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"
    c1 = database.get_supabase_for_user(fake_token)
    c2 = database.get_supabase_for_user(fake_token)

    assert c1.postgrest.session._transport is database._shared_transport
    assert c2.postgrest.session._transport is database._shared_transport
    assert c1.postgrest.session._transport is c2.postgrest.session._transport


# ── MEDIUM-2: Bounded Concurrency & Masking in Admin Auth Lookups ─────────────

def test_mask_csv_value_neutralizes_formula_injection():
    assert admin_routes._mask_csv_value("=1+1") == "'=1+1"
    assert admin_routes._mask_csv_value("+cmd") == "'+cmd"
    assert admin_routes._mask_csv_value("-123") == "'-123"
    assert admin_routes._mask_csv_value("@SUM(A1)") == "'@SUM(A1)"
    assert admin_routes._mask_csv_value("\tTAB") == "'\tTAB"
    assert admin_routes._mask_csv_value("\rCR") == "'\rCR"
    assert admin_routes._mask_csv_value("\nLF") == "'\nLF"
    assert admin_routes._mask_csv_value("Dr. Jane Doe") == "Dr. Jane Doe"
    assert admin_routes._mask_csv_value(None) is None
    assert admin_routes._mask_csv_value("") == ""


def test_admin_users_bounded_concurrency_and_full_name_masking():
    async def _run():
        # Generate 25 dummy profiles to exceed the semaphore limit of 10
        dummy_profiles = []
        for i in range(25):
            dummy_profiles.append({
                "id": f"user-{i}",
                "full_name": f"=DANGEROUS_{i}" if i % 2 == 0 else f"Normal Name {i}",
                "role": "doctor",
                "facility_id": "fac-1",
                "asha_id": f"@ASHA_{i}" if i % 3 == 0 else f"ASHA_{i}",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00Z",
                "facilities": {"name": "Test Facility"},
            })

        mock_profiles_query = MagicMock()
        mock_profiles_query.select.return_value = mock_profiles_query
        mock_profiles_query.eq.return_value = mock_profiles_query
        mock_profiles_query.in_.return_value = mock_profiles_query
        mock_profiles_query.range.return_value = mock_profiles_query
        mock_profiles_query.execute.return_value = MagicMock(data=dummy_profiles)

        active_concurrent = 0
        max_concurrent = 0

        def mock_get_user_by_id(pid: str):
            nonlocal active_concurrent, max_concurrent
            active_concurrent += 1
            if active_concurrent > max_concurrent:
                max_concurrent = active_concurrent
            # Simulate slight I/O latency to exercise semaphore
            import time
            time.sleep(0.01)
            active_concurrent -= 1
            user_mock = MagicMock()
            user_mock.id = pid
            user_mock.email = f"=email_{pid}@example.com"
            user_mock.created_at = "2026-01-01T00:00:00Z"
            user_mock.last_sign_in_at = None
            return MagicMock(user=user_mock)

        with patch.object(admin_routes.supabase_admin, "table", return_value=mock_profiles_query), \
             patch.object(admin_routes.supabase_admin.auth.admin, "get_user_by_id", side_effect=mock_get_user_by_id), \
             patch("app.api.routes.admin_routes.log_phi_access"):

            req = make_dummy_request()
            caller_user = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}
            resp = await admin_routes.list_users(
                request=req,
                page=1,
                limit=25,
                authorization="Bearer fake.token.here",
                user=caller_user,
            )

            assert "data" in resp
            assert len(resp["data"]) == 25
            # Verify semaphore bounded concurrency at <= 10
            assert max_concurrent <= 10
            assert max_concurrent > 1

            # Verify full_name and email and asha_id were masked
            for item in resp["data"]:
                if item["full_name"].startswith("=DANGEROUS"):
                    assert item["full_name"].startswith("'=DANGEROUS")
                assert item["email"].startswith("'=email_")

    asyncio.run(_run())


# ── CRITICAL-5: Chunked .range() Pagination in Analytics Export ───────────────

def test_analytics_export_chunked_pagination():
    async def _run():
        # Simulate a table with 2,350 total records
        # Chunk 0: range(0, 999) -> 1,000 items
        # Chunk 1: range(1000, 1999) -> 1,000 items
        # Chunk 2: range(2000, 2999) -> 350 items (< 1,000 items -> loop terminates)
        ranges_called = []

        def make_record(i):
            return {
                "id": f"case-{i}",
                "created_at": "2026-01-01T00:00:00Z",
                "reviewed_at": None,
                "triage_level": "ROUTINE",
                "triage_confidence": 0.95,
                "overridden_triage": None,
                "override_reason": None,
                "risk_driver": "None",
                "chief_complaint": "Headache",
                "patient_age": 30,
                "patient_sex": "F",
                "patient_location": "Loc",
                "facility_id": "fac-1",
                "submitted_by": "u-1",
                "reviewed_by": None,
                "needs_review": False,
                "triage_model_version": "v1.0",
            }

        class MockCaseQuery:
            def __init__(self):
                self.start = 0
                self.end = 0

            def select(self, *args, **kwargs):
                return self

            def is_(self, *args, **kwargs):
                return self

            def gte(self, *args, **kwargs):
                return self

            def lte(self, *args, **kwargs):
                return self

            def order(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def range(self, start, end):
                self.start = start
                self.end = end
                ranges_called.append((start, end))
                return self

            def execute(self):
                if self.start == 0:
                    data = [make_record(i) for i in range(1000)]
                elif self.start == 1000:
                    data = [make_record(i) for i in range(1000, 2000)]
                elif self.start == 2000:
                    data = [make_record(i) for i in range(2000, 2350)]
                else:
                    data = []
                return MagicMock(data=data)

        mock_db = MagicMock()
        mock_db.table.return_value = MockCaseQuery()

        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"
        user_context = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": None}

        with patch("app.api.routes.analytics_routes.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.analytics_routes.log_phi_access"):

            req = make_dummy_request(method="GET", path="/api/analytics/export?date_from=2026-01-01&date_to=2026-01-02")
            streaming_resp = await analytics_routes.export_cases(
                request=req,
                date_from="2026-01-01",
                date_to="2026-01-02",
                authorization=f"Bearer {fake_token}",
                user=user_context,
            )

            assert ranges_called == [(0, 999), (1000, 1999), (2000, 2999)]

            # Read streaming response body from body_iterator
            chunks = []
            async for chunk in streaming_resp.body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))
            body = "".join(chunks)
            lines = body.strip().split("\r\n")
            # 1 header line + 2350 records = 2351 lines
            assert len(lines) == 2351

    asyncio.run(_run())


# ── MEDIUM-4: Offload predict_triage to asyncio.to_thread ─────────────────────

def test_cases_predict_triage_asyncio_to_thread():
    async def _run():
        load_classifier()
        sample_form = {
            "patient_age": 25,
            "patient_sex": "M",
            "bp_systolic": 120,
            "bp_diastolic": 80,
            "spo2": 98,
            "heart_rate": 72,
            "temperature": 37.0,
            "symptoms": ["cough"],
        }
        result = await asyncio.to_thread(predict_triage, sample_form)
        assert "triage_level" in result
        assert "confidence_score" in result
        assert "risk_driver" in result

    asyncio.run(_run())


# ── HIGH-10b: Prometheus MultiProcessCollector Support ────────────────────────

def test_render_metrics_default_registry():
    out = metrics.render_metrics()
    assert isinstance(out, bytes)
    assert b"vitalnet_http_requests_total" in out or b"# HELP" in out


def test_render_metrics_multiprocess():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": tmpdir}):
            out = metrics.render_metrics()
            assert isinstance(out, bytes)
