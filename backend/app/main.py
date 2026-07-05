"""
VitalNet API — Application entrypoint.
This file is responsible ONLY for:
  1. Structured JSON logging setup
  2. ML model loading at startup (lifespan)
  3. FastAPI app initialization
  4. Middleware registration (CORS, rate limiter, security guards)
  5. Router registration
  6. Global exception handlers

All route logic lives in app/api/routes/.
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import setup_logging
from app.core.correlation import set_correlation_id
from app.core.config import settings
from app.ml.classifier import load_classifier
from app.api.routes import cases, admin_routes, analytics_routes, security, push_routes, referral_routes, dsr_routes, voice_routes, metrics_routes, supervisor_routes

# ── 1. Structured JSON logging — must be first ────────────────────────────────
logger = setup_logging()


# ── 2. ML model lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify DB schema compatibility, then load the ML classifier (degraded/rules-only boot on ML failure)."""
    from app.core.database import validate_schema_compatibility

    try:
        validate_schema_compatibility()
        logger.info("Database schema compatibility check passed")
    except RuntimeError as e:
        logger.critical("CRITICAL: Schema compatibility check failed: %s", e)
        raise
    except Exception as e:
        logger.critical("CRITICAL: Unexpected database schema check failure: %s", e)
        raise RuntimeError(f"Unexpected database schema check failure: {e}") from e

    try:
        loaded = load_classifier()
        if not loaded:
            logger.warning("ML classifier failed to load. Booting in degraded mode (rules-based fallback).")
        else:
            logger.info("ML classifier loaded successfully")
    except Exception as e:
        logger.warning("Unexpected error loading ML classifier: %s. Booting in degraded mode.", e)

    logger.info("VitalNet API started")
    yield
    logger.info("VitalNet API shutting down")


# ── 3. FastAPI app init ───────────────────────────────────────────────────────

_docs_enabled = bool(settings.api_docs_enabled)
_state_changing_methods = {"POST", "PUT", "PATCH", "DELETE"}

app = FastAPI(
    title="VitalNet API",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)


# ── 4. Rate limiter ───────────────────────────────────────────────────────────

app.state.limiter = cases.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ── 5. Response compression — cheap win for weak-hardware / low-bandwidth clients ──

app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=5)


# ── 6. CSRF + device-guard middleware ─────────────────────────────────────────
# Bearer-token auth already stops cross-site forms from acting as an
# authenticated user, but requiring a custom header on every mutating request
# adds defense in depth: a browser only sends a custom header after a CORS
# preflight, and the preflight only succeeds from an allow_origins match. The
# header value itself is not a secret — the protection is the preflight gate.
# X-Device-Id lets future abuse/anomaly detection distinguish devices per user.

@app.middleware("http")
async def csrf_and_device_guard(request: Request, call_next):
    if request.url.path.startswith("/api") and request.method.upper() in _state_changing_methods:
        auth_header = request.headers.get("authorization")
        if auth_header:
            csrf_header = request.headers.get("x-csrf-token", "")
            if csrf_header != settings.csrf_token:
                return JSONResponse(status_code=403, content={"detail": "CSRF token missing or invalid"})
            if not request.headers.get("x-device-id"):
                return JSONResponse(status_code=400, content={"detail": "Missing X-Device-Id header"})
    return await call_next(request)


# ── 7. Security headers — applied to every response ───────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """
    Standard hardening headers. Cache-Control: no-store is deliberate — API
    responses carry patient data and must never be cached by intermediaries or
    the browser. HSTS is only added outside local development.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'self'")
    if settings.environment != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


# ── 8. Correlation ID middleware ──────────────────────────────────────────────

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagates/generates X-Request-ID for request tracing across logs and responses."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        set_correlation_id(correlation_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response


app.add_middleware(CorrelationIdMiddleware)


# ── 8b. Metrics middleware (docs/SLO.md) ──────────────────────────────────────
# Keyed on the matched ROUTE TEMPLATE (e.g. "/api/cases/{case_id}"), read from
# request.scope AFTER call_next() so routing has already resolved it — never
# the raw path, which would give every case_id its own metric label
# (unbounded cardinality, a classic Prometheus footgun).

import time as _time  # noqa: E402
from app.core.metrics import record_request  # noqa: E402


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = _time.monotonic()
        response = await call_next(request)
        duration = _time.monotonic() - start

        # "unmatched" (not the raw path) for a 404/unrouted request — an
        # attacker-controlled raw path would otherwise be an unbounded-
        # cardinality label, a classic Prometheus footgun.
        route = request.scope.get("route")
        route_path = route.path if route else "unmatched"
        record_request(request.method, route_path, response.status_code, duration)

        return response


app.add_middleware(MetricsMiddleware)


# ── 9. CORS — restricted to known origins loaded from settings ────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Device-Id", "X-Request-ID"],
)


# ── 10. Routers ───────────────────────────────────────────────────────────────

app.include_router(cases.router)
app.include_router(admin_routes.router)
app.include_router(analytics_routes.router)
app.include_router(security.router)
app.include_router(push_routes.router)
app.include_router(referral_routes.router)
app.include_router(dsr_routes.router)
app.include_router(voice_routes.router)
app.include_router(metrics_routes.router)
app.include_router(supervisor_routes.router)


# ── 11. Global exception handlers — emit structured JSON, never raw tracebacks ─

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error", extra={"path": str(request.url.path)})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


def _scrub_validation_errors(errors: list) -> list:
    """
    Pydantic v2 error dicts include an 'input' field carrying the value that
    failed validation — for this API that value is patient PII (names, vitals).
    Strip 'input' (and the noisy 'url'/'ctx') so validation errors can be
    logged and returned without leaking patient data into logs or responses.
    """
    return [{k: v for k, v in err.items() if k not in ("input", "url", "ctx")} for err in errors]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = _scrub_validation_errors(exc.errors())
    logger.warning(
        "Validation error",
        extra={"path": str(request.url.path), "errors": safe_errors},
    )
    return JSONResponse(status_code=422, content={"detail": safe_errors})


# ── 12. Health Check ──────────────────────────────────────────────────────────

@app.get("/api/health")
@cases.limiter.limit("120/minute")
async def health(request: Request, authorization: str = Header(default=None)):
    from app.core.database import supabase_anon
    from app.ml.classifier import get_classifier_info
    from app.core.auth import get_current_user

    # 1. Database connectivity check. The exception detail is logged
    # server-side only — never put exception text in the HTTP response, even
    # for the authenticated-diagnostics path below (CodeQL: information
    # exposure through an exception).
    try:
        supabase_anon.table("facilities").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        logger.warning("Health check DB connectivity failed: %s", e)
        db_status = "error"

    # 2. Classifier state
    info = get_classifier_info()
    classifier_loaded = bool(info.get("classifier_type"))
    is_healthy = db_status == "connected" and classifier_loaded

    # 3. Detailed diagnostics only for authenticated clinician/admin callers
    show_diagnostics = False
    if authorization:
        try:
            user = await get_current_user(authorization)
            if user and user.get("resolved_role") in {"doctor", "admin"}:
                show_diagnostics = True
        except Exception:
            pass  # Fall back to the anonymous (basic) response on auth failure

    if show_diagnostics:
        classifier_status = (
            f"loaded — {info['classifier_type']} v{info['model_info'].get('model_version', 'N/A')}"
            if classifier_loaded
            else "NOT LOADED"
        )
        response_body = {
            "status": "ok" if is_healthy else "degraded",
            "database": db_status,
            "classifier": classifier_status,
            "version": "0.3.0",
        }
    else:
        response_body = {
            "status": "ok" if is_healthy else "degraded",
            "version": "0.3.0",
        }

    if not is_healthy:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=response_body)
    return response_body
