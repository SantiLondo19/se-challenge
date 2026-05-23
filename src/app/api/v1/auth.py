"""Authentication endpoints: login, refresh, register."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, UserServiceDep, require_roles
from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.core.rate_limit import limiter
from app.models.user import UserRole
from app.schemas.auth import RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Obtain access + refresh tokens",
    description=(
        "OAuth2 password flow. Submit `application/x-www-form-urlencoded` with "
        "`username` and `password`. Use the access token as `Bearer` for subsequent calls."
    ),
)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthServiceDep,
) -> TokenPair:
    user = await auth_service.authenticate(form.username, form.password)
    return auth_service.issue_tokens(user)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Exchange a refresh token for a fresh token pair",
)
async def refresh(
    request: Request,
    payload: RefreshRequest,
    auth_service: AuthServiceDep,
) -> TokenPair:
    return await auth_service.refresh(payload.refresh_token)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Self-register a new user (regular user role only)",
    description=(
        "Public endpoint when ALLOW_SELF_REGISTER=true. Always creates a "
        "role=`user` account regardless of the requested role. Use "
        "POST /v1/users (admin-only) to create users with arbitrary roles."
    ),
)
async def register(
    request: Request,
    payload: UserCreate,
    user_service: UserServiceDep,
) -> UserRead:
    if not settings.allow_self_register:
        raise ForbiddenError("Self-registration is disabled")
    forced = payload.model_copy(update={"role": UserRole.USER, "active": True})
    user = await user_service.create(forced)
    return UserRead.model_validate(user)


# Optional alias kept for symmetry with the /v1/users admin create endpoint.
@router.post(
    "/register-admin",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Admin-only user creation (any role)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def admin_register(
    request: Request,
    payload: UserCreate,
    user_service: UserServiceDep,
) -> UserRead:
    user = await user_service.create(payload)
    return UserRead.model_validate(user)
