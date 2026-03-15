from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import app.api.auth as auth_api
import app.api.links as links_api
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.link import LinkCreateRequest, LinkUpdateRequest


class FakeScalarResult:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def scalar_one_or_none(self):
        return self._one

    def scalars(self):
        return self

    def all(self):
        return self._many


@dataclass
class FakeDB:
    execute_results: list[FakeScalarResult]

    def __post_init__(self):
        self._idx = 0
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshed = 0

    async def execute(self, *_args, **_kwargs):
        result = self.execute_results[self._idx]
        self._idx += 1
        return result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        if getattr(_obj, "created_at", None) is None:
            _obj.created_at = datetime.now(UTC)
        self.refreshed += 1

    async def delete(self, obj):
        self.deleted.append(obj)


@pytest.mark.asyncio
async def test_auth_register_and_login_direct(monkeypatch):
    db_register = FakeDB(execute_results=[FakeScalarResult(one=None)])
    monkeypatch.setattr(auth_api, "hash_password", lambda _: "hashed")
    monkeypatch.setattr(auth_api, "create_access_token", lambda _: "token123")

    reg_resp = await auth_api.register(
        RegisterRequest(email="unit@example.com", password="12345678"),
        db_register,
    )
    assert reg_resp.access_token == "token123"
    assert db_register.commits == 1
    assert db_register.added

    fake_user = SimpleNamespace(email="unit@example.com", password_hash="hashed")
    db_login = FakeDB(execute_results=[FakeScalarResult(one=fake_user)])
    monkeypatch.setattr(auth_api, "verify_password", lambda p, h: p == "12345678" and h == "hashed")

    login_resp = await auth_api.login(
        LoginRequest(email="unit@example.com", password="12345678"),
        db_login,
    )
    assert login_resp.access_token == "token123"


@pytest.mark.asyncio
async def test_auth_register_duplicate_and_bad_login(monkeypatch):
    existing_user = SimpleNamespace(email="dup@example.com")
    db_dup = FakeDB(execute_results=[FakeScalarResult(one=existing_user)])

    with pytest.raises(HTTPException) as exc:
        await auth_api.register(
            RegisterRequest(email="dup@example.com", password="12345678"),
            db_dup,
        )
    assert exc.value.status_code == 409

    db_bad_login = FakeDB(execute_results=[FakeScalarResult(one=None)])
    with pytest.raises(HTTPException) as login_exc:
        await auth_api.login(
            LoginRequest(email="nobody@example.com", password="12345678"),
            db_bad_login,
        )
    assert login_exc.value.status_code == 401


@pytest.mark.asyncio
async def test_links_create_search_stats_and_history_direct(monkeypatch):
    now = datetime.now(UTC)
    fake_link = SimpleNamespace(
        short_code="alias1",
        original_url="https://x.example",
        created_at=now,
        expires_at=None,
        owner_id=1,
        click_count=0,
        last_accessed_at=None,
    )
    fake_history_item = SimpleNamespace(
        short_code="old",
        original_url="https://old.example",
        created_at=now,
        removed_at=now,
        click_count=3,
        owner_id=1,
        reason="expired",
    )

    db = FakeDB(
        execute_results=[
            FakeScalarResult(one=None),  # _resolve_unique_code(alias)
            FakeScalarResult(many=[fake_link]),  # search
            FakeScalarResult(one=fake_link),  # stats
            FakeScalarResult(many=[fake_history_item]),  # history
        ]
    )
    monkeypatch.setattr(links_api, "cleanup_links", AsyncMock())
    monkeypatch.setattr(links_api, "cache_get", AsyncMock(return_value=None))
    monkeypatch.setattr(links_api, "cache_set", AsyncMock())
    monkeypatch.setattr(links_api, "cache_delete", AsyncMock())

    create_resp = await links_api.create_short_link(
        LinkCreateRequest(original_url="https://x.example", custom_alias="alias1"),
        db,
        user=SimpleNamespace(id=1),
    )
    assert create_resp.short_code == "alias1"

    search_resp = await links_api.search_by_original_url("https://x.example", db)
    assert len(search_resp) == 1

    stats_resp = await links_api.get_link_stats("alias1", db)
    assert stats_resp.short_code == "alias1"

    history_resp = await links_api.expired_history(limit=10, db=db)
    assert history_resp[0]["short_code"] == "old"


@pytest.mark.asyncio
async def test_links_redirect_update_delete_and_errors_direct(monkeypatch):
    now = datetime.now(UTC)
    link = SimpleNamespace(
        short_code="code1",
        original_url="https://redirect.example",
        created_at=now,
        expires_at=None,
        owner_id=11,
        click_count=0,
        last_accessed_at=None,
    )
    db = FakeDB(execute_results=[FakeScalarResult(one=link)])

    monkeypatch.setattr(links_api, "cleanup_links", AsyncMock())
    monkeypatch.setattr(links_api, "cache_get", AsyncMock(return_value={"url": link.original_url}))
    monkeypatch.setattr(links_api, "cache_set", AsyncMock())
    monkeypatch.setattr(links_api, "cache_delete", AsyncMock())

    redirect_resp = await links_api.redirect_to_original("code1", db)
    assert redirect_resp.status_code == 307

    # тут же проверяем ветку update/delete success.
    monkeypatch.setattr(links_api, "_get_link_or_404", AsyncMock(return_value=link))
    update_resp = await links_api.update_link(
        "code1",
        LinkUpdateRequest(original_url="https://new.example"),
        db,
        user=SimpleNamespace(id=11),
    )
    assert update_resp.original_url == "https://new.example/"

    delete_resp = await links_api.delete_link("code1", db, user=SimpleNamespace(id=11))
    assert delete_resp.status_code == 204

    # а тут проверяем оба 403-сценария.
    link.owner_id = 77
    with pytest.raises(HTTPException):
        await links_api.delete_link("code1", db, user=SimpleNamespace(id=11))

    link.owner_id = None
    with pytest.raises(HTTPException):
        await links_api.delete_link("code1", db, user=SimpleNamespace(id=11))


@pytest.mark.asyncio
async def test_links_stats_cached_and_resolve_code_errors(monkeypatch):
    cached_payload = {
        "short_code": "cached1",
        "original_url": "https://cached.example",
        "created_at": datetime.now(UTC).isoformat(),
        "click_count": 99,
        "last_accessed_at": None,
        "expires_at": None,
    }
    monkeypatch.setattr(links_api, "cache_get", AsyncMock(return_value=cached_payload))
    monkeypatch.setattr(links_api, "cleanup_links", AsyncMock())
    db_stats = FakeDB(execute_results=[])
    stats = await links_api.get_link_stats("cached1", db_stats)
    assert stats.click_count == 99

    # alias уже занят -> 409.
    db_alias_taken = FakeDB(execute_results=[FakeScalarResult(one=SimpleNamespace())])
    with pytest.raises(HTTPException) as alias_exc:
        await links_api._resolve_unique_code(db_alias_taken, custom_alias="x")
    assert alias_exc.value.status_code == 409

    # генерация не смогла подобрать уникальный код -> 500.
    db_full = FakeDB(execute_results=[FakeScalarResult(one=SimpleNamespace()) for _ in range(10)])
    monkeypatch.setattr(links_api, "generate_short_code", lambda: "same_code")
    with pytest.raises(HTTPException) as gen_exc:
        await links_api._resolve_unique_code(db_full, custom_alias=None, attempts=10)
    assert gen_exc.value.status_code == 500


@pytest.mark.asyncio
async def test_links_cached_redirect_missing_object_branch(monkeypatch):
    db = FakeDB(execute_results=[FakeScalarResult(one=None)])
    monkeypatch.setattr(links_api, "cleanup_links", AsyncMock())
    monkeypatch.setattr(links_api, "cache_get", AsyncMock(return_value={"url": "https://x"}))
    monkeypatch.setattr(links_api, "cache_delete", AsyncMock())
    monkeypatch.setattr(links_api, "cache_set", AsyncMock())

    with pytest.raises(HTTPException) as exc:
        await links_api.redirect_to_original("missing", db)
    assert exc.value.status_code == 404
