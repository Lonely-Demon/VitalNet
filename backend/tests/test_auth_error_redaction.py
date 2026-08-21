"""Authentication boundary tests for client-safe failure responses."""

import asyncio

import pytest
from fastapi import HTTPException

from app.core import auth


def test_token_verification_exception_is_not_echoed(monkeypatch, caplog):
    sensitive_detail = "upstream-verifier-detail-with-internal-url"

    def fail_verification(_token: str) -> dict:
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr(auth, "_verify_token", fail_verification)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(auth.get_current_user("Bearer synthetic.header.payload"))

    assert raised.value.status_code == 401
    assert raised.value.detail == "Invalid or expired token"
    assert sensitive_detail not in str(raised.value.detail)
    assert "JWT verification failed" in caplog.text
