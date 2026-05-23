"""v1 router aggregates per-resource subrouters."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, users

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth.router)
v1_router.include_router(users.router)

__all__ = ["v1_router"]
