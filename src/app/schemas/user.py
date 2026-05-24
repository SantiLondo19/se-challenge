"""User wire schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.models.user import UserRole


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: UserRole = UserRole.USER
    active: bool = True

    model_config = ConfigDict(use_enum_values=False)


class UserCreate(UserBase):
    password: SecretStr = Field(min_length=8, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "jdoe",
                "email": "jdoe@example.com",
                "first_name": "Jane",
                "last_name": "Doe",
                "role": "user",
                "active": True,
                "password": "StrongPass123!",
            }
        }
    )


class UserUpdate(BaseModel):
    """All fields optional; only present fields are updated."""

    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    active: bool | None = None
    password: SecretStr | None = Field(default=None, min_length=8, max_length=128)


class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=False)


class UserFilter(BaseModel):
    """Query parameters for the list endpoint."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    role: UserRole | None = None
    active: bool | None = None
    search: str | None = Field(
        default=None, max_length=100, description="Match username/email/name"
    )
