import logging
import sys
from pythonjsonlogger import jsonlogger

from app.core.correlation import get_correlation_id


class CorrelationIdLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that automatically adds correlation ID to log records.
    """
    
    def process(self, msg, kwargs):
        # Add correlation_id to extra if not already present
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        if "correlation_id" not in kwargs["extra"]:
            correlation_id = get_correlation_id()
            if correlation_id:
                kwargs["extra"]["correlation_id"] = correlation_id
        return msg, kwargs


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
        "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s "
        "%(correlation_id)s"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    return logging.getLogger("vitalnet")
