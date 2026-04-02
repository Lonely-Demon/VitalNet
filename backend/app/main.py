"""
VitalNet API — Application entrypoint.
This file is responsible ONLY for:
  1. Structured JSON logging setup
  2. ML model loading at startup (lifespan)
  3. FastAPI app initialization
  4. Middleware registration (CORS, rate limiter)
  5. Router registration
  6. Global exception handlers

All route logic lives in app/api/routes/.
"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import setup_logging, set_correlation_id
from app.core.config import settings
from app.ml.classifier import load_classifier
from app.api.routes import cases, admin_routes, analytics_routes

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

app = FastAPI(title="VitalNet API", version="0.2.0", lifespan=lifespan)


# ── 4. Rate limiter ───────────────────────────────────────────────────────────

app.state.limiter = cases.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ── 4b. Correlation ID middleware ─────────────────────────────────────────────

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


# ── 5. CORS — restricted to known origins loaded from settings ────────────────

_allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
if settings.frontend_url:
    _allowed_origins.append(settings.frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 6. Routers ────────────────────────────────────────────────────────────────

app.include_router(cases.router)
app.include_router(admin_routes.router)
app.include_router(analytics_routes.router)


# ── 7. Global exception handlers — emit structured JSON, never raw tracebacks ─

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


# ── 8. Health Check ───────────────────────────────────────────────────────────

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

    return {
        "status": "ok" if db_status == "connected" and classifier_loaded else "degraded",
        "database": db_status,
        "classifier": classifier_status,
        "version": "0.2.0",
    }
