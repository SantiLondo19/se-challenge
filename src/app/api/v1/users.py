"""User CRUD endpoints."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import CurrentUser, UserServiceDep, require_roles
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserFilter, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=Page[UserRead],
    summary="List users (admin only)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def list_users(
    request: Request,
    user_service: UserServiceDep,
    filters: Annotated[UserFilter, Query()],
) -> Page[UserRead]:
    return await user_service.list_users(filters)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create user (admin only, any role)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def create_user(
    request: Request,
    payload: UserCreate,
    user_service: UserServiceDep,
) -> UserRead:
    user = await user_service.create(payload)
    return UserRead.model_validate(user)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get currently authenticated user",
)
async def read_me(request: Request, current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update currently authenticated user",
)
async def update_me(
    request: Request,
    payload: UserUpdate,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserRead:
    user = await user_service.update(current_user.id, payload, caller=current_user)
    return UserRead.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user by id (admin or self)",
)
async def read_user(
    request: Request,
    user_id: UUID,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserRead:
    user = await user_service.get_for_caller(user_id, caller=current_user)
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user by id (admin, or self for own profile)",
)
async def update_user(
    request: Request,
    user_id: UUID,
    payload: UserUpdate,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> UserRead:
    user = await user_service.update(user_id, payload, caller=current_user)
    return UserRead.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate user (admin only, soft delete)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def delete_user(
    request: Request,
    user_id: UUID,
    current_user: CurrentUser,
    user_service: UserServiceDep,
) -> None:
    await user_service.delete(user_id, caller=current_user)
