import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()
redis_client: Redis | None = None


async def init_cache() -> None:
    global redis_client
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def close_cache() -> None:
    if redis_client is not None:
        try:
            await redis_client.close()
        except Exception:
            # если редис временно недоступен, не валим graceful shutdown.
            return


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    if redis_client is None:
        return
    data = json.dumps(value, default=str)
    try:
        await redis_client.set(key, data, ex=ttl or settings.cache_ttl_seconds)
    except Exception:
        # деградируем в no-cache режим, но endpoint продолжает работать.
        return


async def cache_get(key: str) -> Any | None:
    if redis_client is None:
        return None
    try:
        data = await redis_client.get(key)
    except Exception:
        return None
    if data is None:
        return None
    return json.loads(data)


async def cache_delete(*keys: str) -> None:
    if redis_client is None or not keys:
        return
    try:
        await redis_client.delete(*keys)
    except Exception:
        return
