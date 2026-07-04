"""
Request correlation ID storage — a single contextvar shared by the logging
formatter (core/logging.py) and route handlers, so a ID set in the request
middleware is visible everywhere that logs or reads it within that request.
"""
from contextvars import ContextVar

_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    return _correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id_var.set(correlation_id)
