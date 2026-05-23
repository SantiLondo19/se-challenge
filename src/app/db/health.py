"""Database liveness check used by the /healthz endpoint."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ping_db(session: AsyncSession) -> bool:
    result = await session.execute(text("SELECT 1"))
    return result.scalar() == 1
