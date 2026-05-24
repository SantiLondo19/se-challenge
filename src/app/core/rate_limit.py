"""Rate-limiter singleton. Keys by authenticated user id when present, else IP."""
from __future__ import annotations

from typing import TYPE_CHECKING

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

if TYPE_CHECKING:
    from starlette.requests import Request


def _key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key, default_limits=[settings.rate_limit_default])
