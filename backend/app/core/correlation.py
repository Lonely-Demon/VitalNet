"""
Request Correlation ID utilities for observability.

This module provides request-scoped correlation ID storage using Python's
contextvars, allowing correlation IDs to be propagated across async tasks
within a single request lifecycle.
"""
import uuid
from contextvars import ContextVar
from typing import Optional

# Request-scoped correlation ID storage
# Uses contextvars to ensure thread-safety in async contexts
_correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> Optional[str]:
    """
    Get the current request's correlation ID.
    
    Returns:
        The correlation ID for the current request, or None if not set.
    """
    return _correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current request context.
    
    Args:
        correlation_id: The unique correlation ID to set.
    """
    _correlation_id_var.set(correlation_id)


def generate_correlation_id() -> str:
    """
    Generate a new unique correlation ID.
    
    Returns:
        A new UUID string to use as a correlation ID.
    """
    return str(uuid.uuid4())


class CorrelationIdContext:
    """
    Context manager for temporarily setting a correlation ID.
    
    Usage:
        with CorrelationIdContext("my-correlation-id"):
            # correlation ID is available here
            pass
    """
    
    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.token: Optional[object] = None
    
    def __enter__(self) -> str:
        self.token = _correlation_id_var.set(self.correlation_id)
        return self.correlation_id
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.token is not None:
            _correlation_id_var.reset(self.token)