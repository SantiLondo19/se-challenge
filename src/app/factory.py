"""FastAPI application factory. Wires lifespan, middleware, routers, exception handlers."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api import api_router, register_exception_handlers
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import install_middleware
from app.core.rate_limit import limiter
from app.db.session import dispose_engine


API_DESCRIPTION = """
REST API for user management built with **FastAPI + SQLAlchemy 2.0 async + PostgreSQL**.

## Features
- JWT access + refresh tokens with role-based access control (`admin` / `user` / `guest`).
- Full user CRUD with pagination, filtering, and search.
- Rate limiting, structured JSON logging, request-id propagation, security headers.

## Auth flow (try it from this page)
1. Call `POST /v1/auth/register` (or use a seeded account).
2. Call `POST /v1/auth/login` with `username` + `password` (form-urlencoded).
3. Copy the returned `access_token`.
4. Click **Authorize** (top right) and paste the token. All protected endpoints unlock.

## Error format
Every error returns:
```json
{ "code": "conflict", "message": "User with this username or email already exists" }
```
Common codes: `validation_error` (422), `unauthorized` (401), `forbidden` (403),
`not_found` (404), `conflict` (409), `rate_limited` (429), `internal_error` (500).
"""

OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "auth",
        "description": (
            "Authentication and session management. `login` returns a JWT pair; "
            "`refresh` rotates them; `register` self-creates a `user` account "
            "when `ALLOW_SELF_REGISTER=true`."
        ),
    },
    {
        "name": "users",
        "description": (
            "User CRUD. `/me` works for any authenticated caller. List, create, "
            "and delete are admin-only. Reads/updates by id are admin-or-self."
        ),
    },
    {
        "name": "health",
        "description": "Liveness / readiness probe. Reports app + DB status.",
    },
]


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger("app.lifespan")
    logger.info("startup", env=settings.env)
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("shutdown")


def _rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "code": "rate_limited",
            "message": f"Rate limit exceeded: {exc.detail}",
        },
        headers={"Retry-After": "60"},
    )


def _custom_openapi(app: FastAPI) -> Any:
    """Inject a `BearerAuth` (raw JWT) scheme alongside the existing OAuth2 password flow.

    The OAuth2 flow already powers Swagger's `Authorize` button after a login form
    submission. `BearerAuth` lets API consumers paste a token obtained out of band
    (e.g. from `curl` or a test) without re-running the form.
    """

    def _build() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste a raw JWT access token obtained from `/v1/auth/login`.",
        }
        schema["info"]["contact"] = {
            "name": "Advana SE Challenge",
            "url": "https://github.com/",
        }
        schema["info"]["license"] = {
            "name": "MIT",
            "url": "https://opensource.org/license/mit/",
        }
        app.openapi_schema = schema
        return schema

    return _build


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="User Management API",
        description=API_DESCRIPTION,
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "filter": True,
            "tryItOutEnabled": True,
        },
        contact={"name": "Advana SE Challenge"},
        license_info={"name": "MIT", "url": "https://opensource.org/license/mit/"},
    )

    # Rate limiter wiring
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    install_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_router)

    app.openapi = _custom_openapi(app)  # type: ignore[method-assign]

    return app
