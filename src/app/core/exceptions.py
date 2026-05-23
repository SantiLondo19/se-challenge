"""Domain exceptions mapped to HTTP responses by api.errors handlers."""
from __future__ import annotations


class AppError(Exception):
    """Base application error. Carries an HTTP status, a stable code, and a message."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "Internal server error") -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
