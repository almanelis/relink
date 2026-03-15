from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.auth import router as auth_router
from app.api.links import redirect_to_original, router as links_router
from app.db.base import Base
from app.db.session import get_db
import app.api.links as links_module
import app.tasks.cleanup as cleanup_module


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(links_router)

    @app.get("/{short_code}", include_in_schema=False)
    async def root_redirect(
        short_code: str, db: AsyncSession = Depends(get_db)
    ):  # pragma: no cover - тонкий прокси-роут
        return await redirect_to_original(short_code, db)

    return app


@pytest_asyncio.fixture
async def db_sessionmaker(tmp_path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    # тут используем sqlite-файл на каждый тест: чисто, изолированно, красиво.
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_maker
    await engine.dispose()


@pytest.fixture
def fake_cache(monkeypatch) -> dict[str, object]:
    storage: dict[str, object] = {}

    async def _get(key: str):
        return storage.get(key)

    async def _set(key: str, value, ttl=None):
        storage[key] = value

    async def _delete(*keys: str):
        for key in keys:
            storage.pop(key, None)

    monkeypatch.setattr(links_module, "cache_get", _get)
    monkeypatch.setattr(links_module, "cache_set", _set)
    monkeypatch.setattr(links_module, "cache_delete", _delete)
    monkeypatch.setattr(cleanup_module, "cache_delete", _delete)
    return storage


@pytest_asyncio.fixture
async def client(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_cache: dict[str, object]
) -> AsyncGenerator[AsyncClient, None]:
    app = build_test_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(db_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    async with db_sessionmaker() as session:
        yield session
