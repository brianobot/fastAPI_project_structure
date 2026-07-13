import json
from typing import Any, cast

import redis.asyncio as redis

from app.settings import settings


class RedisManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )

    async def cache_json_item(
        self, key: str, value: dict[str, Any], ttl: int = 3600
    ) -> None:
        value_as_string = json.dumps(value)
        await self.redis_client.set(name=key, value=value_as_string, ex=ttl)

    async def get_json_item(
        self, key: str, default: None = None
    ) -> dict[str, Any] | None:
        value = await self.redis_client.get(name=key)

        if value is None:
            return default

        value_decoded = json.loads(cast(str, value))
        return value_decoded

    async def delete_key(self, key: str) -> None:
        await self.redis_client.delete(key)

    async def get_int(self, key: str) -> int:
        value = await self.redis_client.get(name=key)
        return int(value) if value is not None else 0

    async def increment(self, key: str, ttl: int | None = None) -> int:
        # Atomic INCR. When ttl is given, the expiry is set on first increment
        # so the counter decays as a fixed window (used for failure lockouts).
        value = await self.redis_client.incr(key)
        if ttl is not None and value == 1:
            await self.redis_client.expire(key, ttl)
        return value


redis_manager = RedisManager()
