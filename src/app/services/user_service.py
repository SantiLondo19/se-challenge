"""User business logic. Owns uniqueness, password hashing, RBAC self-vs-admin rules."""
from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserFilter, UserRead, UserUpdate

_logger = get_logger("service.user")


class UserService:
    def __init__(self, session: AsyncSession, repo: UserRepository) -> None:
        self.session = session
        self.repo = repo

    async def create(self, payload: UserCreate) -> User:
        if await self.repo.exists_by_email_or_username(
            email=payload.email, username=payload.username
        ):
            raise ConflictError("User with this username or email already exists")

        user = User(
            username=payload.username,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            role=payload.role,
            active=payload.active,
            password_hash=hash_password(payload.password.get_secret_value()),
        )
        user = await self.repo.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        _logger.info("user_created", user_id=str(user.id), role=user.role.value)
        return user

    async def get(self, user_id: UUID) -> User:
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def get_for_caller(self, target_id: UUID, caller: User) -> User:
        """Read a user: admin sees anyone, others only themselves."""
        if caller.role != UserRole.ADMIN and caller.id != target_id:
            raise ForbiddenError("You can only access your own profile")
        return await self.get(target_id)

    async def list_users(self, filters: UserFilter) -> Page[UserRead]:
        items, total = await self.repo.list_paginated(filters)
        pages = math.ceil(total / filters.size) if filters.size else 0
        return Page[UserRead](
            items=[UserRead.model_validate(u) for u in items],
            total=total,
            page=filters.page,
            size=filters.size,
            pages=pages,
        )

    async def update(
        self,
        target_id: UUID,
        payload: UserUpdate,
        caller: User,
    ) -> User:
        target = await self.get(target_id)

        is_self = caller.id == target.id
        is_admin = caller.role == UserRole.ADMIN
        if not (is_self or is_admin):
            raise ForbiddenError("You can only update your own profile")

        # Non-admins cannot change role or active fields.
        if not is_admin:
            if payload.role is not None and payload.role != target.role:
                raise ForbiddenError("Only admins can change role")
            if payload.active is not None and payload.active != target.active:
                raise ForbiddenError("Only admins can change active state")

        changes = payload.model_dump(exclude_unset=True, exclude={"password"})
        if payload.email and payload.email.lower() != target.email.lower():
            if await self.repo.exists_by_email_or_username(email=payload.email):
                raise ConflictError("Email already in use")
        if payload.password is not None:
            changes["password_hash"] = hash_password(payload.password.get_secret_value())

        user = await self.repo.update(target, **changes)
        await self.session.commit()
        await self.session.refresh(user)
        _logger.info("user_updated", user_id=str(user.id), fields=list(changes))
        return user

    async def delete(self, target_id: UUID, caller: User) -> None:
        if caller.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can delete users")
        if caller.id == target_id:
            raise ConflictError("Admin cannot delete their own account")

        target = await self.get(target_id)
        # Soft delete: prefer deactivating to preserve referential history.
        await self.repo.update(target, active=False)
        await self.session.commit()
        _logger.info("user_deactivated", user_id=str(target_id))
