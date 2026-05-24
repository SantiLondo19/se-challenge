"""Unit tests for AuthService with mocked repository."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import AuthError
from app.core.security import create_refresh_token
from app.models.user import UserRole
from app.services.auth_service import AuthService
from tests.factories import make_user

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_authenticate_succeeds_with_valid_credentials():
    repo = AsyncMock()
    user = make_user(role="user", password="GoodPass123!")
    repo.get_by_username.return_value = user
    svc = AuthService(repo=repo)
    result = await svc.authenticate("user_test", "GoodPass123!")
    assert result.id == user.id


@pytest.mark.asyncio
async def test_authenticate_fails_on_unknown_user():
    repo = AsyncMock()
    repo.get_by_username.return_value = None
    svc = AuthService(repo=repo)
    with pytest.raises(AuthError):
        await svc.authenticate("ghost", "anything")


@pytest.mark.asyncio
async def test_authenticate_fails_on_wrong_password():
    repo = AsyncMock()
    user = make_user(password="GoodPass123!")
    repo.get_by_username.return_value = user
    svc = AuthService(repo=repo)
    with pytest.raises(AuthError):
        await svc.authenticate(user.username, "BadPass!!!")


@pytest.mark.asyncio
async def test_authenticate_fails_on_inactive_account():
    repo = AsyncMock()
    user = make_user(password="GoodPass123!", active=False)
    repo.get_by_username.return_value = user
    svc = AuthService(repo=repo)
    with pytest.raises(AuthError):
        await svc.authenticate(user.username, "GoodPass123!")


@pytest.mark.asyncio
async def test_issue_tokens_returns_pair():
    repo = AsyncMock()
    user = make_user(role=UserRole.ADMIN)
    svc = AuthService(repo=repo)
    pair = svc.issue_tokens(user)
    assert pair.access_token
    assert pair.refresh_token
    assert pair.access_token != pair.refresh_token
    assert pair.expires_in > 0


@pytest.mark.asyncio
async def test_refresh_succeeds_with_valid_token():
    repo = AsyncMock()
    user = make_user(role=UserRole.USER)
    repo.get.return_value = user
    svc = AuthService(repo=repo)
    refresh = create_refresh_token(str(user.id), user.role.value)
    pair = await svc.refresh(refresh)
    assert pair.access_token


@pytest.mark.asyncio
async def test_refresh_fails_with_access_token():
    repo = AsyncMock()
    svc = AuthService(repo=repo)
    from app.core.security import create_access_token
    access = create_access_token("x", "user")
    with pytest.raises(AuthError):
        await svc.refresh(access)
