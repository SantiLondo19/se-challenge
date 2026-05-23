"""Common Pydantic schemas: pagination, errors, health."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int = Field(ge=0, description="Total number of items matching filters")
    page: int = Field(ge=1, description="Current page (1-indexed)")
    size: int = Field(ge=1, description="Page size")
    pages: int = Field(ge=0, description="Total number of pages")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 20,
            "pages": 0,
        }
    })


class ErrorResponse(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: dict | None = None


class HealthResponse(BaseModel):
    status: str = Field(description="overall status: 'ok' or 'degraded'")
    db: str = Field(description="database status: 'ok' or 'down'")
    version: str
