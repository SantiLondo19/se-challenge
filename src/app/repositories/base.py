"""Generic async repository over an arbitrary ORM model."""
from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Pure data-access. Returns ORM objects. Never raises domain errors."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def get_by(self, **kwargs: Any) -> ModelT | None:
        stmt = select(self.model).filter_by(**kwargs).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        return int((await self.session.execute(stmt)).scalar_one())

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: ModelT, **changes: Any) -> ModelT:
        for k, v in changes.items():
            setattr(entity, k, v)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def delete_by_id(self, entity_id: UUID) -> int:
        stmt = delete(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.rowcount or 0
