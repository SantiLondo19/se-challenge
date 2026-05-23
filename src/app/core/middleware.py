"""HTTP middleware: request id propagation and security response headers."""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from starlette.types import ASGIApp


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate/propagate X-Request-Id and bind it to the structlog context."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        trace_header = request.headers.get("X-Cloud-Trace-Context", "")
        trace_id = trace_header.split("/", 1)[0] if trace_header else None

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            **({"trace": trace_id} if trace_id else {}),
        )

        logger = get_logger("http.access")
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed")
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_completed", status_code=response.status_code, elapsed_ms=round(elapsed_ms, 2)
        )

        response.headers["X-Request-Id"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP-recommended security response headers."""

    def __init__(self, app: "ASGIApp", *, is_production: bool) -> None:
        super().__init__(app)
        self._is_production = is_production

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "()")
        if self._is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response


def install_middleware(app) -> None:  # type: ignore[no-untyped-def]
    """Order matters: outermost first → innermost last (FastAPI adds in reverse)."""
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        SecurityHeadersMiddleware,
        is_production=settings.is_production,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    )
