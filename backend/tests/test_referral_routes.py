"""
Unit tests for referral routes (BUG-28, BUG-36).
Covers:
- BUG-28: Facility ordering prioritized by tier hierarchy and district proximity
- BUG-36: Prevention of duplicate active referrals on the same case (409 Conflict)
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes import referral_routes
from app.api.routes.referral_routes import CreateReferralRequest


CASE_ID = "11111111-1111-4111-8111-111111111111"
FACILITY_CALLER_ID = "22222222-2222-4222-8222-222222222222"
FACILITY_TARGET_ID = "33333333-3333-4333-8333-333333333333"


def make_dummy_request(method="GET", path="/api/facilities"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_list_active_facilities_ordered_by_tier_and_district_proximity():
    """
    BUG-28: Facilities must be sorted by:
    1. Tier hierarchy: district_hospital (0) < chc (2) < phc (3)
    2. District proximity: same district as caller prioritized
    3. Capacity status
    4. Open case count
    5. Name
    """
    async def _run():
        facilities_data = [
            {"id": "fac-phc-same", "name": "PHC Alpha", "type": "phc", "district": "District 1", "capacity_status": "available"},
            {"id": "fac-dh-other", "name": "District Hospital Beta", "type": "district_hospital", "district": "District 2", "capacity_status": "available"},
            {"id": "fac-chc-same", "name": "CHC Gamma", "type": "chc", "district": "District 1", "capacity_status": "available"},
            {"id": "fac-dh-same", "name": "District Hospital Alpha", "type": "district_hospital", "district": "District 1", "capacity_status": "available"},
            {"id": "fac-chc-other", "name": "CHC Delta", "type": "chc", "district": "District 2", "capacity_status": "available"},
        ]

        class MockFacilityQuery:
            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def neq(self, *args, **kwargs):
                return self

            def order(self, *args, **kwargs):
                return self

            def maybe_single(self):
                return self

            def execute(self):
                # When looking up caller district
                return MagicMock(data={"district": "District 1"})

        class MockListQuery:
            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def neq(self, *args, **kwargs):
                return self

            def order(self, *args, **kwargs):
                return self

            def execute(self):
                return MagicMock(data=[dict(f) for f in facilities_data])

        mock_db = MagicMock()
        def mock_table(table_name):
            if table_name == "facilities":
                # Returns MockListQuery or MockFacilityQuery
                q = MockListQuery()
                q.maybe_single = lambda: MagicMock(execute=lambda: MagicMock(data={"district": "District 1"}))
                return q
            return MagicMock()

        mock_db.table.side_effect = mock_table
        mock_db.rpc.return_value.execute.return_value = MagicMock(data=[])

        user = {"sub": "doc-1", "resolved_role": "doctor", "resolved_facility_id": FACILITY_CALLER_ID}
        req = make_dummy_request()

        with patch("app.api.routes.referral_routes.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.referral_routes.extract_bearer_token", return_value="token-123"):

            result = await referral_routes.list_active_facilities(
                request=req,
                authorization="Bearer token-123",
                user=user,
            )

            # Expected ordering:
            # 1. District Hospital in same district (fac-dh-same)
            # 2. District Hospital in other district (fac-dh-other)
            # 3. CHC in same district (fac-chc-same)
            # 4. CHC in other district (fac-chc-other)
            # 5. PHC in same district (fac-phc-same)
            ids_in_order = [f["id"] for f in result]
            assert ids_in_order == [
                "fac-dh-same",
                "fac-dh-other",
                "fac-chc-same",
                "fac-chc-other",
                "fac-phc-same",
            ]

    asyncio.run(_run())


def test_create_referral_rejects_active_duplicate():
    """
    BUG-36: create_referral must check for an existing active referral (pending,
    acknowledged, patient_arrived) on the same case and raise 409 Conflict.
    """
    async def _run():
        mock_case = {
            "id": CASE_ID,
            "facility_id": FACILITY_CALLER_ID,
            "deleted_at": None,
            "chief_complaint": "Severe chest pain",
            "patient_age": 55,
            "patient_sex": "male",
            "triage_level": "EMERGENCY",
        }

        mock_active_referral = {
            "id": "ref-active-1",
            "status": "pending",
        }

        class MockCaseQuery:
            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def maybe_single(self):
                return self

            def execute(self):
                return MagicMock(data=mock_case)

        class MockReferralQuery:
            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def in_(self, col, vals):
                return self

            def limit(self, count):
                return self

            def execute(self):
                return MagicMock(data=[mock_active_referral])

        mock_db = MagicMock()
        def mock_table(table_name):
            if table_name == "case_records":
                return MockCaseQuery()
            elif table_name == "referrals":
                return MockReferralQuery()
            return MagicMock()

        mock_db.table.side_effect = mock_table

        user = {"sub": "doc-1", "resolved_role": "doctor", "resolved_facility_id": FACILITY_CALLER_ID}
        req = make_dummy_request(method="POST", path=f"/api/cases/{CASE_ID}/refer")
        body = CreateReferralRequest(
            receiving_facility_id=FACILITY_TARGET_ID,
            reason="Cardiology specialist evaluation needed",
            urgency="EMERGENCY",
        )

        with patch("app.api.routes.referral_routes.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.referral_routes.extract_bearer_token", return_value="token-123"):

            with pytest.raises(HTTPException) as exc_info:
                await referral_routes.create_referral(
                    request=req,
                    case_id=CASE_ID,
                    body=body,
                    authorization="Bearer token-123",
                    user=user,
                )
            assert exc_info.value.status_code == 409
            assert "An active referral already exists for this case" in exc_info.value.detail

    asyncio.run(_run())
