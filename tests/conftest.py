"""Shared pytest fixtures.

Strategy:
- Unit tests (`tests/unit`) use AsyncMock repos and need no DB.
- Integration tests (`tests/integration`) spin up Postgres via testcontainers,
  run Alembic migrations, then run each test inside a SAVEPOINT that is rolled
  back at teardown. Set SKIP_INTEGRATION=1 to skip when Docker is unavailable.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

    from app.models.user import User


SKIP_INTEGRATION = os.environ.get("SKIP_INTEGRATION") == "1"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def pg_url() -> AsyncIterator[str]:
    if SKIP_INTEGRATION:
        pytest.skip("Integration tests disabled via SKIP_INTEGRATION=1")

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    try:
        raw_url = container.get_connection_url()
        # testcontainers returns psycopg2 url; rewrite for asyncpg
        async_url = raw_url.replace("postgresql+psycopg2", "postgresql+asyncpg").replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        yield async_url
    finally:
        container.stop()


@pytest_asyncio.fixture(scope="session")
async def engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    os.environ["DATABASE_URL"] = pg_url
    os.environ["JWT_SECRET"] = "test-secret-key-must-be-long-enough"
    os.environ["ENV"] = "test"
    os.environ["RATE_LIMIT_DEFAULT"] = "10000/minute"
    os.environ["RATE_LIMIT_LOGIN"] = "10000/minute"

    # Reset cached settings + recreate engine with new env
    from app.core import config as core_config
    core_config.get_settings.cache_clear()
    core_config.settings = core_config.get_settings()

    from sqlalchemy.ext.asyncio import create_async_engine
    new_engine = create_async_engine(pg_url, future=True)

    # Run migrations against the fresh DB
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    cfg.set_main_option("sqlalchemy.url", pg_url)
    # Alembic runs in a sync context; use asyncio.to_thread because env.py manages its own loop
    await asyncio.to_thread(command.upgrade, cfg, "head")

    yield new_engine
    await new_engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test session with rollback isolation."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> FastAPI:
    from app.db.session import get_session
    from app.factory import create_app

    application = create_app()

    async def _override_session():
        yield db_session

    application.dependency_overrides[get_session] = _override_session
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------- Domain fixtures ----------

@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    from tests.factories import make_user

    user = make_user(role="admin", username="admin_test", email="admin@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    from tests.factories import make_user

    user = make_user(role="user", username="user_test", email="user@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def guest_user(db_session: AsyncSession) -> User:
    from tests.factories import make_user

    user = make_user(role="guest", username="guest_test", email="guest@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(str(user.id), user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    return _auth_headers(admin_user)


@pytest.fixture
def user_headers(regular_user: User) -> dict[str, str]:
    return _auth_headers(regular_user)


@pytest.fixture
def guest_headers(guest_user: User) -> dict[str, str]:
    return _auth_headers(guest_user)
