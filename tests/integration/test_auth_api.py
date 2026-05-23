"""End-to-end tests for /v1/auth/* endpoints."""
from __future__ import annotations

import pytest

from tests.factories import user_create_payload

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_register_creates_regular_user(client):
    payload = user_create_payload(role="admin")  # role override should be ignored
    r = await client.post("/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == payload["username"]
    assert body["role"] == "user"  # forced to user
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_register_rejects_duplicate_username(client):
    payload = user_create_payload()
    r1 = await client.post("/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert r2.json()["code"] == "conflict"


@pytest.mark.asyncio
async def test_register_validates_email(client):
    payload = user_create_payload()
    payload["email"] = "not-an-email"
    r = await client.post("/v1/auth/register", json=payload)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_validates_password_length(client):
    payload = user_create_payload()
    payload["password"] = "short"
    r = await client.post("/v1/auth/register", json=payload)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_returns_token_pair(client):
    payload = user_create_payload(password="StrongPass123!")
    await client.post("/v1/auth/register", json=payload)

    r = await client.post(
        "/v1/auth/login",
        data={"username": payload["username"], "password": "StrongPass123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(client):
    payload = user_create_payload(password="StrongPass123!")
    await client.post("/v1/auth/register", json=payload)

    r = await client.post(
        "/v1/auth/login",
        data={"username": payload["username"], "password": "WrongPass!!"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_new_pair(client):
    payload = user_create_payload(password="StrongPass123!")
    await client.post("/v1/auth/register", json=payload)
    r = await client.post(
        "/v1/auth/login",
        data={"username": payload["username"], "password": "StrongPass123!"},
    )
    refresh = r.json()["refresh_token"]
    r2 = await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    body = r2.json()
    assert body["access_token"]
    assert body["refresh_token"]
