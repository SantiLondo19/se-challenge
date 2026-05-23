"""Unit tests for UserService with mocked repository and session."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserFilter, UserUpdate
from app.services.user_service import UserService
from tests.factories import make_user

pytestmark = pytest.mark.unit


def _service_with_repo() -> tuple[UserService, AsyncMock, AsyncMock]:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    repo = AsyncMock()
    svc = UserService(session=session, repo=repo)
    return svc, repo, session


@pytest.mark.asyncio
async def test_create_raises_on_existing_user():
    svc, repo, _ = _service_with_repo()
    repo.exists_by_email_or_username.return_value = True
    payload = UserCreate(
        username="dup",
        email="dup@x.com",
        first_name="A",
        last_name="B",
        password="StrongPass123!",
    )
    with pytest.raises(ConflictError):
        await svc.create(payload)


@pytest.mark.asyncio
async def test_create_hashes_password_and_persists():
    svc, repo, session = _service_with_repo()
    repo.exists_by_email_or_username.return_value = False
    repo.add.side_effect = lambda u: u
    payload = UserCreate(
        username="newbie",
        email="newbie@x.com",
        first_name="N",
        last_name="B",
        password="StrongPass123!",
    )
    user = await svc.create(payload)
    repo.add.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert user.password_hash != "StrongPass123!"
    assert user.password_hash.startswith("$2")


@pytest.mark.asyncio
async def test_get_raises_not_found():
    svc, repo, _ = _service_with_repo()
    repo.get.return_value = None
    with pytest.raises(NotFoundError):
        await svc.get(uuid4())


@pytest.mark.asyncio
async def test_get_for_caller_admin_can_read_anyone():
    svc, repo, _ = _service_with_repo()
    target = make_user(role="user")
    admin = make_user(role="admin")
    repo.get.return_value = target
    result = await svc.get_for_caller(target.id, caller=admin)
    assert result is target


@pytest.mark.asyncio
async def test_get_for_caller_user_cannot_read_others():
    svc, repo, _ = _service_with_repo()
    other = make_user(role="user")
    caller = make_user(role="user")
    repo.get.return_value = other
    with pytest.raises(ForbiddenError):
        await svc.get_for_caller(other.id, caller=caller)


@pytest.mark.asyncio
async def test_list_users_paginates():
    svc, repo, _ = _service_with_repo()
    users = [make_user(role="user") for _ in range(3)]
    repo.list_paginated.return_value = (users, 25)
    page = await svc.list_users(UserFilter(page=1, size=10))
    assert page.total == 25
    assert page.pages == 3
    assert len(page.items) == 3


@pytest.mark.asyncio
async def test_update_non_admin_cannot_change_role():
    svc, repo, _ = _service_with_repo()
    target = make_user(role=UserRole.USER)
    repo.get.return_value = target
    payload = UserUpdate(role=UserRole.ADMIN)
    with pytest.raises(ForbiddenError):
        await svc.update(target.id, payload, caller=target)


@pytest.mark.asyncio
async def test_update_admin_can_change_role():
    svc, repo, session = _service_with_repo()
    target = make_user(role=UserRole.USER)
    admin = make_user(role=UserRole.ADMIN)
    repo.get.return_value = target
    repo.update.side_effect = lambda u, **changes: User(
        **{
            **{k: getattr(u, k) for k in [
                "id", "username", "email", "first_name", "last_name",
                "password_hash", "role", "active",
            ]},
            **changes,
        }
    )
    payload = UserUpdate(role=UserRole.ADMIN)
    updated = await svc.update(target.id, payload, caller=admin)
    assert updated.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_delete_requires_admin():
    svc, repo, _ = _service_with_repo()
    user = make_user(role=UserRole.USER)
    with pytest.raises(ForbiddenError):
        await svc.delete(user.id, caller=user)


@pytest.mark.asyncio
async def test_delete_admin_cannot_delete_self():
    svc, repo, _ = _service_with_repo()
    admin = make_user(role=UserRole.ADMIN)
    with pytest.raises(ConflictError):
        await svc.delete(admin.id, caller=admin)
