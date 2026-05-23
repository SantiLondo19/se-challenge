"""RBAC matrix: admin vs user vs guest."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_me(client):
    r = await client.get("/v1/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client):
    r = await client.get("/v1/users/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_guest_can_read_own_profile(client, guest_headers):
    r = await client.get("/v1/users/me", headers=guest_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "guest"


@pytest.mark.asyncio
async def test_guest_cannot_list_users(client, guest_headers):
    r = await client.get("/v1/users", headers=guest_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_guest_cannot_create_user(client, guest_headers):
    from tests.factories import user_create_payload

    r = await client.post("/v1/users", json=user_create_payload(), headers=guest_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_role_can_do_everything(client, admin_headers):
    r1 = await client.get("/v1/users/me", headers=admin_headers)
    r2 = await client.get("/v1/users", headers=admin_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
