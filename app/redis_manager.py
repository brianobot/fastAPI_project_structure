import json
from typing import Any, cast

import redis

from app.settings import Settings

settings = Settings()  # type: ignore


class RedisManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )

    def cache_json_item(self, key: str, value: dict[str, Any], ttl: int = 3600) -> None:
        value_as_string = json.dumps(value)
        self.redis_client.set(name=key, value=value_as_string, ex=ttl)

    def get_json_item(self, key: str, default: None = None) -> dict[str, Any] | None:
        value = self.redis_client.get(name=key)

        if value is None:
            return default

        value_decoded = json.loads(cast(str, value))
        return value_decoded

    def delete_key(self, key: str) -> None:
        self.redis_client.delete(key)


redis_manager = RedisManager()
