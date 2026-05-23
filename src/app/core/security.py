"""Password hashing and JWT primitives. Stateless, no DB."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _create_token(subject: str, role: str, token_type: TokenType, ttl: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject, role, "access", timedelta(minutes=settings.access_token_ttl_minutes)
    )


def create_refresh_token(subject: str, role: str) -> str:
    return _create_token(
        subject, role, "refresh", timedelta(days=settings.refresh_token_ttl_days)
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decode and verify a JWT. Raises AuthError on any failure."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise AuthError(f"Invalid token: {e}") from e

    if payload.get("type") != expected_type:
        raise AuthError(f"Expected {expected_type} token, got {payload.get('type')}")
    if "sub" not in payload:
        raise AuthError("Token missing subject")
    return payload
