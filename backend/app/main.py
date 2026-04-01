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
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import admin_routes, analytics_routes, cases, security
from app.core.config import settings
from app.core.logging import setup_logging
from app.ml.classifier import load_classifier

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

# ── 6. Security middleware ────────────────────────────────────────────────────


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


# ── 7. CORS — restricted to known origins loaded from settings ────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Device-Id"],
)


# ── 8. Routers ────────────────────────────────────────────────────────────────

app.include_router(cases.router)
app.include_router(admin_routes.router)
app.include_router(analytics_routes.router)
app.include_router(security.router)


# ── 9. Global exception handlers — emit structured JSON, never raw tracebacks ─


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: Exception):
    if isinstance(exc, RateLimitExceeded):
        return _rate_limit_exceeded_handler(request, exc)
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error", extra={"path": str(request.url.path)})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "Validation error",
        extra={"path": str(request.url.path), "errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# ── 10. Health Check ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    from app.core.database import supabase_anon
    from app.ml.classifier import get_classifier_info

    # Database connectivity check
    try:
        supabase_anon.table("facilities").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:80]}" # Truncate — never expose full errors

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
