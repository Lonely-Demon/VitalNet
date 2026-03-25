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
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
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

app = FastAPI(title="VitalNet API", version="0.2.0", lifespan=lifespan)


# ── 4. Rate limiter ───────────────────────────────────────────────────────────

app.state.limiter = cases.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


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
