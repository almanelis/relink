import pytest

import app.services.cache as cache_module


class FakeRedis:
    def __init__(self):
        self.storage: dict[str, str] = {}
        self.closed = False

    async def set(self, key: str, value: str, ex: int | None = None):
        self.storage[key] = value

    async def get(self, key: str):
        return self.storage.get(key)

    async def delete(self, *keys: str):
        for key in keys:
            self.storage.pop(key, None)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_cache_set_get_delete_roundtrip(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache_module, "redis_client", fake)

    await cache_module.cache_set("k1", {"a": 1}, ttl=10)
    payload = await cache_module.cache_get("k1")
    assert payload == {"a": 1}

    await cache_module.cache_delete("k1")
    assert await cache_module.cache_get("k1") is None


@pytest.mark.asyncio
async def test_init_and_close_cache(monkeypatch):
    fake = FakeRedis()

    class FakeRedisFactory:
        @staticmethod
        def from_url(url: str, decode_responses: bool = False):
            return fake

    monkeypatch.setattr(cache_module, "Redis", FakeRedisFactory)
    await cache_module.init_cache()
    assert cache_module.redis_client is fake

    await cache_module.close_cache()
    assert fake.closed is True
