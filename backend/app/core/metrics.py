"""
Prometheus metrics (docs/SLO.md). A small, deliberately narrow metric set —
request rate/latency/errors per route, plus the one business metric that
matters clinically (triage classifications by level) — not an
instrument-everything approach. Exposed at GET /api/metrics, admin-only
(see app/api/routes/metrics_routes.py).
"""
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "vitalnet_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)

REQUEST_LATENCY = Histogram(
    "vitalnet_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
)

TRIAGE_CLASSIFICATIONS = Counter(
    "vitalnet_triage_classifications_total",
    "Triage classifications produced, by level",
    ["triage_level"],
)


def record_request(method: str, route: str, status_code: int, duration_seconds: float) -> None:
    REQUEST_COUNT.labels(method=method, route=route, status=str(status_code)).inc()
    REQUEST_LATENCY.labels(method=method, route=route).observe(duration_seconds)


def record_triage_classification(triage_level: str) -> None:
    TRIAGE_CLASSIFICATIONS.labels(triage_level=triage_level).inc()


def render_metrics() -> bytes:
    return generate_latest()


METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST
