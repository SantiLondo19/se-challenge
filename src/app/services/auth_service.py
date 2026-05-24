"""Authentication and token issuance."""
from __future__ import annotations

from uuid import UUID

from app.core.config import settings
from app.core.exceptions import AuthError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPair

_logger = get_logger("service.auth")

# Pre-computed bcrypt hash used to keep authenticate() timing roughly constant
# against username enumeration when the user lookup misses.
_DUMMY_HASH = hash_password("__missing_user_dummy__")


class AuthService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    async def authenticate(self, username: str, password: str) -> User:
        user = await self.repo.get_by_username(username)
        if user is None:
            verify_password(password, _DUMMY_HASH)
            raise AuthError("Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise AuthError("Invalid credentials")
        if not user.active:
            raise AuthError("Account is inactive")
        return user

    def issue_tokens(self, user: User) -> TokenPair:
        access = create_access_token(str(user.id), user.role.value)
        refresh = create_refresh_token(str(user.id), user.role.value)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            expires_in=settings.access_token_ttl_minutes * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self.repo.get(UUID(payload["sub"]))
        if user is None or not user.active:
            raise AuthError("User no longer active")
        _logger.info("token_refreshed", user_id=str(user.id))
        return self.issue_tokens(user)

    async def current_user(self, access_token: str) -> User:
        payload = decode_token(access_token, expected_type="access")
        user = await self.repo.get(UUID(payload["sub"]))
        if user is None:
            raise AuthError("User not found")
        if not user.active:
            raise AuthError("Account is inactive")
        return user
