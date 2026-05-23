"""Authentication wire schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "access_token": "eyJhbGciOi...",
            "refresh_token": "eyJhbGciOi...",
            "token_type": "bearer",
            "expires_in": 900,
        }
    })
