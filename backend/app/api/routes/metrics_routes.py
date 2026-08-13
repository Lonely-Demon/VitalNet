"""
Prometheus metrics endpoint (docs/SLO.md). Admin-only — same access-control
posture as the rest of the admin surface (require_role('admin') is the
boundary, no RLS involved since this reads in-process counters, not a
database table). Configure a Prometheus scrape job with a bearer token for
an admin service account — see docs/SLO.md for the scrape config snippet.
"""
from fastapi import APIRouter, Depends, Header, Request, Response

from app.core.auth import require_role
from app.core.metrics import METRICS_CONTENT_TYPE, render_metrics
from app.api.routes.cases import limiter

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
@limiter.limit("60/minute")
async def metrics(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("admin")),
):
    return Response(content=render_metrics(), media_type=METRICS_CONTENT_TYPE)
