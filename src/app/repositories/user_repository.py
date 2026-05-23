"""Persistence layer for the User aggregate."""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository
from app.schemas.user import UserFilter


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(func.lower(User.username) == username.lower()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_paginated(self, filters: UserFilter) -> tuple[list[User], int]:
        """Return (items, total) for the given filters."""
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)

        conditions = []
        if filters.role is not None:
            conditions.append(User.role == filters.role)
        if filters.active is not None:
            conditions.append(User.active.is_(filters.active))
        if filters.search:
            like = f"%{filters.search.lower()}%"
            conditions.append(
                or_(
                    func.lower(User.username).like(like),
                    func.lower(User.email).like(like),
                    func.lower(User.first_name).like(like),
                    func.lower(User.last_name).like(like),
                )
            )
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        stmt = (
            stmt.order_by(User.created_at.desc())
            .offset((filters.page - 1) * filters.size)
            .limit(filters.size)
        )

        items = list((await self.session.execute(stmt)).scalars().all())
        total = int((await self.session.execute(count_stmt)).scalar_one())
        return items, total

    async def exists_by_email_or_username(
        self,
        *,
        email: str | None = None,
        username: str | None = None,
    ) -> bool:
        conditions = []
        if email is not None:
            conditions.append(func.lower(User.email) == email.lower())
        if username is not None:
            conditions.append(func.lower(User.username) == username.lower())
        if not conditions:
            return False
        stmt = select(User.id).where(or_(*conditions)).limit(1)
        return (await self.session.execute(stmt)).first() is not None

    async def count_by_role(self, role: UserRole) -> int:
        stmt = select(func.count()).select_from(User).where(User.role == role)
        return int((await self.session.execute(stmt)).scalar_one())
