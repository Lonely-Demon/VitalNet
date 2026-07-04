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

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.logging import setup_logging
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

app = FastAPI(title="VitalNet API", version="0.3.0", lifespan=lifespan)


# ── 4. Rate limiter ───────────────────────────────────────────────────────────

app.state.limiter = cases.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ── 5. Security headers — applied to every response ───────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """
    Standard hardening headers. Cache-Control: no-store is deliberate — API
    responses carry patient data and must never be cached by intermediaries or
    the browser. HSTS is opt-in via settings (off for local HTTP dev).
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if settings.security_headers_hsts:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── 6. CORS — restricted to known origins loaded from settings ────────────────

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
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── 7. Routers ────────────────────────────────────────────────────────────────

app.include_router(cases.router)
app.include_router(admin_routes.router)
app.include_router(analytics_routes.router)


# ── 8. Global exception handlers — emit structured JSON, never raw tracebacks ─

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
    Strip 'input' (and the noisy 'url') so validation errors can be logged and
    returned without leaking patient data into logs or error responses.
    """
    scrubbed = []
    for err in errors:
        scrubbed.append({k: v for k, v in err.items() if k not in ("input", "url", "ctx")})
    return scrubbed


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = _scrub_validation_errors(exc.errors())
    logger.warning(
        "Validation error",
        extra={"path": str(request.url.path), "errors": safe_errors},
    )
    return JSONResponse(status_code=422, content={"detail": safe_errors})


# ── 9. Health Check ───────────────────────────────────────────────────────────

@app.get("/api/health")
@cases.limiter.limit("120/minute")
async def health(request: Request):
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
        "version": "0.3.0",
    }
