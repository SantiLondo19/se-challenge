"""Top-level API router. Mounts all versioned routers + health/utility endpoints."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import SessionDep
from app.api.v1 import v1_router
from app.db.health import ping_db
from app.schemas.common import HealthResponse

api_router = APIRouter()
api_router.include_router(v1_router)


@api_router.get(
    "/healthz",
    response_model=HealthResponse,
    tags=["health"],
    status_code=status.HTTP_200_OK,
    summary="Liveness + DB ping",
)
async def healthz(session: SessionDep) -> HealthResponse:
    try:
        db_ok = await ping_db(session)
    except Exception:
        db_ok = False
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db="ok" if db_ok else "down",
        version="0.1.0",
    )


__all__ = ["api_router"]
