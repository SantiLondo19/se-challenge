"""End-to-end tests for /v1/users CRUD endpoints."""
from __future__ import annotations

import pytest

from tests.factories import user_create_payload

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_admin_can_create_user(client, admin_headers):
    payload = user_create_payload(role="user")
    r = await client.post("/v1/users", json=payload, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["username"] == payload["username"]


@pytest.mark.asyncio
async def test_admin_can_create_admin_user(client, admin_headers):
    payload = user_create_payload(role="admin")
    r = await client.post("/v1/users", json=payload, headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_create_user_requires_admin(client, user_headers):
    payload = user_create_payload(role="user")
    r = await client.post("/v1/users", json=payload, headers=user_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_without_auth_returns_401(client):
    payload = user_create_payload(role="user")
    r = await client.post("/v1/users", json=payload)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_users_admin_only(client, admin_headers, user_headers):
    r_admin = await client.get("/v1/users", headers=admin_headers)
    assert r_admin.status_code == 200
    body = r_admin.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body

    r_user = await client.get("/v1/users", headers=user_headers)
    assert r_user.status_code == 403


@pytest.mark.asyncio
async def test_list_pagination(client, admin_headers):
    for _ in range(5):
        await client.post("/v1/users", json=user_create_payload(), headers=admin_headers)
    r = await client.get("/v1/users?page=1&size=2", headers=admin_headers)
    body = r.json()
    assert body["size"] == 2
    assert len(body["items"]) <= 2


@pytest.mark.asyncio
async def test_list_filter_by_role(client, admin_headers):
    await client.post(
        "/v1/users", json=user_create_payload(role="guest"), headers=admin_headers
    )
    r = await client.get("/v1/users?role=guest", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["role"] == "guest"


@pytest.mark.asyncio
async def test_list_filter_by_active(client, admin_headers):
    r = await client.get("/v1/users?active=true", headers=admin_headers)
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["active"] is True


@pytest.mark.asyncio
async def test_list_search(client, admin_headers):
    payload = user_create_payload(username="searchable_unique_handle")
    await client.post("/v1/users", json=payload, headers=admin_headers)
    r = await client.get("/v1/users?search=searchable_unique", headers=admin_headers)
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()["items"]]
    assert "searchable_unique_handle" in usernames


@pytest.mark.asyncio
async def test_get_me_returns_current_user(client, user_headers, regular_user):
    r = await client.get("/v1/users/me", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["id"] == str(regular_user.id)


@pytest.mark.asyncio
async def test_update_me_changes_fields(client, user_headers):
    r = await client.patch(
        "/v1/users/me",
        json={"first_name": "Updated"},
        headers=user_headers,
    )
    assert r.status_code == 200
    assert r.json()["first_name"] == "Updated"


@pytest.mark.asyncio
async def test_update_me_cannot_escalate_role(client, user_headers):
    r = await client.patch(
        "/v1/users/me",
        json={"role": "admin"},
        headers=user_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_user_by_id_admin(client, admin_headers, regular_user):
    r = await client.get(f"/v1/users/{regular_user.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["id"] == str(regular_user.id)


@pytest.mark.asyncio
async def test_get_user_self(client, user_headers, regular_user):
    r = await client.get(f"/v1/users/{regular_user.id}", headers=user_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_other_user_forbidden(client, user_headers, admin_user):
    r = await client.get(f"/v1/users/{admin_user.id}", headers=user_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_nonexistent_returns_404(client, admin_headers):
    from uuid import uuid4

    r = await client.get(f"/v1/users/{uuid4()}", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_update_user(client, admin_headers, regular_user):
    r = await client.patch(
        f"/v1/users/{regular_user.id}",
        json={"last_name": "Renamed"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["last_name"] == "Renamed"


@pytest.mark.asyncio
async def test_admin_delete_deactivates_user(client, admin_headers, regular_user):
    r = await client.delete(f"/v1/users/{regular_user.id}", headers=admin_headers)
    assert r.status_code == 204

    r2 = await client.get(f"/v1/users/{regular_user.id}", headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["active"] is False


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(client, admin_headers, admin_user):
    r = await client.delete(f"/v1/users/{admin_user.id}", headers=admin_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_delete_requires_admin(client, user_headers, admin_user):
    r = await client.delete(f"/v1/users/{admin_user.id}", headers=user_headers)
    assert r.status_code == 403
