import logging
import sys
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger

# Context variable to store correlation ID for the current request
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get the correlation ID for the current request context."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current request context."""
    correlation_id_var.set(correlation_id)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation_id to each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


def setup_logging() -> logging.Logger:
    """
    Configure the root logger with a JSON formatter so every log line is
    machine-parseable by cloud platforms (Railway, Datadog, AWS CloudWatch).
    Call once at application startup before any other imports emit logs.
    Returns the named 'vitalnet' logger for use across the application.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove any handlers already attached (e.g. uvicorn's default handler)
    while root_logger.handlers:
        root_logger.handlers.pop()

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s %(correlation_id)s"
    )
    handler.setFormatter(formatter)
    # Add correlation ID filter to include it in all log entries
    handler.addFilter(CorrelationIdFilter())
    root_logger.addHandler(handler)

    return logging.getLogger("vitalnet")
