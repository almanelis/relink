from datetime import UTC, datetime

import pytest


async def _register_and_get_token(client, email: str) -> str:
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "12345678"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_full_links_happy_path(client):
    token = await _register_and_get_token(client, "owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/links/shorten",
        headers=headers,
        json={
            "original_url": "https://example.com",
            "custom_alias": "myalias",
            "expires_at": "2099-01-01T10:00:00Z",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["short_code"] == "myalias"

    stats_before = await client.get("/links/myalias/stats")
    assert stats_before.status_code == 200
    assert stats_before.json()["click_count"] == 0

    redirect_resp = await client.get("/links/myalias", follow_redirects=False)
    assert redirect_resp.status_code == 307
    assert redirect_resp.headers["location"] == "https://example.com/"

    # проверяем и "красивый" корневой маршрут /{short_code}.
    root_redirect_resp = await client.get("/myalias", follow_redirects=False)
    assert root_redirect_resp.status_code == 307

    stats_after = await client.get("/links/myalias/stats")
    assert stats_after.status_code == 200
    assert stats_after.json()["click_count"] == 2
    assert stats_after.json()["last_accessed_at"] is not None

    search_resp = await client.get(
        "/links/search", params={"original_url": "https://example.com/"}
    )
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 1
    assert search_resp.json()[0]["short_code"] == "myalias"

    update_resp = await client.put(
        "/links/myalias",
        headers=headers,
        json={"original_url": "https://fastapi.tiangolo.com"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["original_url"] == "https://fastapi.tiangolo.com/"

    delete_resp = await client.delete("/links/myalias", headers=headers)
    assert delete_resp.status_code == 204

    missing_after_delete = await client.get("/links/myalias/stats")
    assert missing_after_delete.status_code == 404


@pytest.mark.asyncio
async def test_alias_collision_and_validation_errors(client):
    token = await _register_and_get_token(client, "alias@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(
        "/links/shorten",
        headers=headers,
        json={"original_url": "https://example.org", "custom_alias": "dup"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/links/shorten",
        headers=headers,
        json={"original_url": "https://example.net", "custom_alias": "dup"},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Alias already exists"

    bad_url = await client.post(
        "/links/shorten",
        headers=headers,
        json={"original_url": "not-a-url"},
    )
    assert bad_url.status_code == 422

    bad_expires = await client.post(
        "/links/shorten",
        headers=headers,
        json={
            "original_url": "https://example.com",
            "custom_alias": "badtime",
            "expires_at": "2099-01-01T10:00:13Z",
        },
    )
    assert bad_expires.status_code == 422


@pytest.mark.asyncio
async def test_permissions_for_update_delete_and_anonymous_links(client):
    owner_token = await _register_and_get_token(client, "owner2@example.com")
    stranger_token = await _register_and_get_token(client, "stranger@example.com")

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    create_owned = await client.post(
        "/links/shorten",
        headers=owner_headers,
        json={"original_url": "https://owned.example", "custom_alias": "owned"},
    )
    assert create_owned.status_code == 201

    unauth_update = await client.put(
        "/links/owned", json={"original_url": "https://new.example"}
    )
    assert unauth_update.status_code == 401

    forbidden_update = await client.put(
        "/links/owned",
        headers=stranger_headers,
        json={"original_url": "https://new.example"},
    )
    assert forbidden_update.status_code == 403

    forbidden_delete = await client.delete("/links/owned", headers=stranger_headers)
    assert forbidden_delete.status_code == 403

    # ссылка без авторизации получает owner_id = null и управляться не должна.
    create_anon = await client.post(
        "/links/shorten",
        json={"original_url": "https://anon.example", "custom_alias": "anonlink"},
    )
    assert create_anon.status_code == 201

    delete_anon = await client.delete("/links/anonlink", headers=owner_headers)
    assert delete_anon.status_code == 403
    assert "Anonymous links cannot be managed" in delete_anon.json()["detail"]


@pytest.mark.asyncio
async def test_expired_history_endpoint(client, db_session):
    from app.models.expired_link import ExpiredLink

    db_session.add(
        ExpiredLink(
            short_code="old1",
            original_url="https://old.example",
            created_at=datetime.now(UTC),
            click_count=5,
            owner_id=1,
            reason="expired",
        )
    )
    await db_session.commit()

    response = await client.get("/links/expired/history")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["short_code"] == "old1"
    assert payload[0]["reason"] == "expired"
