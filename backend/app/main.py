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
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import setup_logging, set_correlation_id
from app.core.config import settings
from app.ml.classifier import load_classifier
from app.api.routes import cases, admin_routes, analytics_routes, security

# ── 1. Structured JSON logging — must be first ────────────────────────────────
logger = setup_logging()


# ── 2. ML model lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the ML classifier once at startup; release on shutdown."""
    load_classifier()
    logger.info("VitalNet API started")
    yield
    logger.info("VitalNet API shutting down")


# ── 3. FastAPI app init ───────────────────────────────────────────────────────

_docs_enabled = bool(settings.api_docs_enabled)
_state_changing_methods = {"POST", "PUT", "PATCH", "DELETE"}

app = FastAPI(
    title="VitalNet API",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)


# ── 4. Rate limiter ───────────────────────────────────────────────────────────

app.state.limiter = cases.limiter
app.add_middleware(SlowAPIMiddleware)


# ── 5. Response compression ───────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=5)


# ── 6. CSRF and Device Guard Middleware ───────────────────────────────────────

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


# ── 7. Security Headers Middleware ────────────────────────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'self'")
    if settings.environment.lower() != "development":
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    return response


# ── 8. Correlation ID Middleware ──────────────────────────────────────────────

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate/extract and propagate X-Request-ID for request tracing.
    - Extracts X-Request-ID from incoming request headers if present
    - Generates a new UUID if not provided
    - Adds correlation ID to request state for access in route handlers
    - Includes correlation ID in response headers
    - Sets correlation ID in logging context for all log entries
    """

    async def dispatch(self, request: Request, call_next):
        # Extract correlation ID from header or generate new one
        correlation_id = request.headers.get("X-Request-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Set correlation ID in request state for route handlers
        request.state.correlation_id = correlation_id

        # Set correlation ID in logging context
        set_correlation_id(correlation_id)

        # Process the request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Request-ID"] = correlation_id

        return response


app.add_middleware(CorrelationIdMiddleware)


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


# ── 11. Global exception handlers — emit structured JSON, never raw tracebacks ─

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    logger.warning(
        "Rate limit exceeded",
        extra={"path": str(request.url.path), "correlation_id": correlation_id},
    )
    return _rate_limit_exceeded_handler(request, exc)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    logger.exception(
        "Unhandled server error",
        extra={"path": str(request.url.path), "correlation_id": correlation_id},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    logger.warning(
        "Validation error",
        extra={"path": str(request.url.path), "errors": exc.errors(), "correlation_id": correlation_id},
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# ── 12. Health Check ──────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    from app.core.database import supabase_anon
    from app.ml.classifier import get_classifier_info

    # Database connectivity check
    try:
        supabase_anon.table("facilities").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:80]}"  # Truncate — never expose full errors

    # Classifier state
    info = get_classifier_info()
    classifier_loaded = bool(info["classifier_type"])
    classifier_status = (
        f"loaded — {info['classifier_type']} v{info['model_info'].get('model_version', 'N/A')}"
        if classifier_loaded
        else "NOT LOADED"
    )

    is_healthy = db_status == "connected" and classifier_loaded
    response_body = {
        "status": "ok" if is_healthy else "degraded",
        "database": db_status,
        "classifier": classifier_status,
        "version": "0.2.0",
    }

    # Return 503 Service Unavailable when degraded
    if not is_healthy:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=response_body)
    return response_body
