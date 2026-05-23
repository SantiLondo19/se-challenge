"""Shared FastAPI dependencies for the API layer."""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import structlog
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.db.session import get_session
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=True)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_user_service(session: SessionDep, repo: UserRepoDep) -> UserService:
    return UserService(session, repo)


def get_auth_service(repo: UserRepoDep) -> AuthService:
    return AuthService(repo)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    auth_service: AuthServiceDep,
) -> User:
    user = await auth_service.current_user(token)
    # Stash on request.state for rate-limit key + log context.
    request.state.user_id = str(user.id)
    structlog.contextvars.bind_contextvars(user_id=str(user.id), role=user.role.value)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: UserRole) -> Callable[[User], User]:
    """Dependency factory: ensures the current user has one of the allowed roles."""

    async def _check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError(
                f"Requires role in {[r.value for r in allowed]}, got {user.role.value}"
            )
        return user

    return _check
