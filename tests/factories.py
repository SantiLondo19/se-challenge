"""Deterministic factories for tests."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.security import hash_password
from app.models.user import User, UserRole

_DEFAULT_PASSWORD = "TestPass123!"


def make_user(
    *,
    role: str | UserRole = UserRole.USER,
    username: str | None = None,
    email: str | None = None,
    first_name: str = "Test",
    last_name: str = "User",
    password: str = _DEFAULT_PASSWORD,
    active: bool = True,
    id: UUID | None = None,
    **kw: Any,
) -> User:
    if isinstance(role, str):
        role = UserRole(role)
    suffix = uuid4().hex[:8]
    now = datetime.now(UTC)
    return User(
        id=id or uuid4(),
        username=username or f"user_{suffix}",
        email=email or f"user_{suffix}@example.com",
        first_name=first_name,
        last_name=last_name,
        password_hash=hash_password(password),
        role=role,
        active=active,
        created_at=now,
        updated_at=now,
        **kw,
    )


def user_create_payload(
    *,
    username: str | None = None,
    email: str | None = None,
    role: str = "user",
    password: str = _DEFAULT_PASSWORD,
) -> dict[str, Any]:
    suffix = uuid4().hex[:8]
    return {
        "username": username or f"new_{suffix}",
        "email": email or f"new_{suffix}@example.com",
        "first_name": "New",
        "last_name": "Person",
        "role": role,
        "active": True,
        "password": password,
    }
