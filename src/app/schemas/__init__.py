"""Pydantic wire schemas. Boundary DTOs between HTTP and services."""
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.common import ErrorResponse, HealthResponse, Page
from app.schemas.user import UserBase, UserCreate, UserFilter, UserRead, UserUpdate

__all__ = [
    "ErrorResponse",
    "HealthResponse",
    "LoginRequest",
    "Page",
    "RefreshRequest",
    "TokenPair",
    "UserBase",
    "UserCreate",
    "UserFilter",
    "UserRead",
    "UserUpdate",
]
