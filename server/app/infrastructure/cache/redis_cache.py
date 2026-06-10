from __future__ import annotations

from typing import Any

from loguru import logger
from redis.asyncio import Redis


class RedisCache:
    """Thin wrapper around Redis for common caching operations."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        value = await self._client.get(key)
        return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if ttl is not None:
            await self._client.setex(key, ttl, value)
        else:
            await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def expire(self, key: str, ttl: int) -> None:
        await self._client.expire(key, ttl)

    async def hget(self, key: str, field: str) -> str | None:
        value = await self._client.hget(key, field)
        return value

    async def hset(self, key: str, field: str, value: str) -> None:
        await self._client.hset(key, field, value)

    async def hgetall(self, key: str) -> dict[str, str]:
        result = await self._client.hgetall(key)
        return {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in result.items()}  # type: ignore[union-attr]

    async def incr(self, key: str) -> int:
        return await self._client.incr(key)

    async def lock(self, key: str, ttl: int = 10) -> bool:
        """Acquire a distributed lock. Returns True if acquired."""
        result = await self._client.setnx(f"lock:{key}", "1")
        if result:
            await self._client.expire(f"lock:{key}", ttl)
            return True
        return False

    async def unlock(self, key: str) -> None:
        await self._client.delete(f"lock:{key}")

    async def close(self) -> None:
        await self._client.aclose()
        logger.debug("Redis cache connection closed")
