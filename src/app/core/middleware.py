"""HTTP middleware: request id propagation and security response headers.

Implemented as pure ASGI middleware (no `BaseHTTPMiddleware`) so they do not
spawn anyio sub-tasks that can detach asyncpg connections from the running
event loop during pytest-asyncio runs.
"""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.logging import get_logger


class RequestIdMiddleware:
    """Generate/propagate X-Request-Id and bind it to the structlog context."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_in = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        request_id = headers_in.get("x-request-id") or uuid.uuid4().hex
        trace_header = headers_in.get("x-cloud-trace-context", "")
        trace_id = trace_header.split("/", 1)[0] if trace_header else None

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=scope.get("path", ""),
            method=scope.get("method", ""),
            **({"trace": trace_id} if trace_id else {}),
        )

        logger = get_logger("http.access")
        start = time.perf_counter()
        status_holder: dict[str, int] = {"code": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message.get("status", 0)
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-Id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("request_failed")
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_completed",
            status_code=status_holder["code"],
            elapsed_ms=round(elapsed_ms, 2),
        )


class SecurityHeadersMiddleware:
    """OWASP-recommended security response headers."""

    def __init__(self, app: ASGIApp, *, is_production: bool) -> None:
        self.app = app
        self._is_production = is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault("Permissions-Policy", "()")
                if self._is_production:
                    headers.setdefault(
                        "Strict-Transport-Security",
                        "max-age=63072000; includeSubDomains; preload",
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)


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
