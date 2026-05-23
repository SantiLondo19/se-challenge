"""Unit tests for password hashing and JWT encode/decode."""
from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import patch

import pytest

from app.core.exceptions import AuthError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


pytestmark = pytest.mark.unit


def test_password_roundtrip():
    h = hash_password("CorrectHorseBatteryStaple")
    assert h != "CorrectHorseBatteryStaple"
    assert verify_password("CorrectHorseBatteryStaple", h) is True
    assert verify_password("wrong", h) is False


def test_access_token_roundtrip():
    token = create_access_token("user-id-123", "admin")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-id-123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token("user-id-123", "user")
    payload = decode_token(token, expected_type="refresh")
    assert payload["type"] == "refresh"


def test_decode_rejects_wrong_type():
    access = create_access_token("u", "user")
    with pytest.raises(AuthError):
        decode_token(access, expected_type="refresh")


def test_decode_rejects_tampered_token():
    token = create_access_token("u", "user")
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    with pytest.raises(AuthError):
        decode_token(tampered, expected_type="access")


def test_decode_rejects_expired_token():
    # Patch the TTL setting to a negative value to force immediate expiry
    with patch("app.core.security.settings") as mock_settings:
        mock_settings.jwt_secret.get_secret_value.return_value = "test-secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl_minutes = 0
        mock_settings.refresh_token_ttl_days = 0
        token = create_access_token("u", "user")
    # Sleep a tick so exp is in the past
    time.sleep(1)
    with pytest.raises(AuthError):
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.jwt_secret.get_secret_value.return_value = "test-secret"
            mock_settings.jwt_algorithm = "HS256"
            decode_token(token, expected_type="access")


def test_decode_rejects_garbage():
    with pytest.raises(AuthError):
        decode_token("not.a.jwt", expected_type="access")
