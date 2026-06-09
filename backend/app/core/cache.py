import json
import logging
from typing import Any

import redis.asyncio as aioredis
import redis

from app.core.config import get_settings

logger = logging.getLogger("cache")

settings = get_settings()

TTL_BY_PREFIX: dict[str, int] = {
    "rankings:": 300,
    "groups:": 300,
    "probabilities:": 300,
    "calibration:": 1800,
    "benchmark:": 1800,
    "refinement:": 1800,
    "simulations:": 3600,
    "dashboard:": 120,
    "teams:": 600,
    "matches:": 600,
    "predictions:": 300,
}

DEFAULT_TTL = 300

cache_hits = 0
cache_misses = 0


def _get_ttl(key: str) -> int:
    for prefix, ttl in TTL_BY_PREFIX.items():
        if key.startswith(prefix):
            return ttl
    return DEFAULT_TTL


class RedisCacheService:
    def __init__(self):
        self._sync: redis.Redis | None = None
        self._async: aioredis.Redis | None = None

    def _get_sync(self) -> redis.Redis:
        if self._sync is None:
            self._sync = redis.from_url(settings.redis_url, decode_responses=True)
        return self._sync

    async def _get_async(self) -> aioredis.Redis:
        if self._async is None:
            self._async = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._async

    def ping(self) -> bool:
        try:
            client = self._get_sync()
            return client.ping()
        except redis.RedisError:
            return False

    def get_sync(self, key: str) -> Any | None:
        global cache_hits, cache_misses
        try:
            client = self._get_sync()
            val = client.get(key)
            if val is not None:
                cache_hits += 1
                return json.loads(val)
            cache_misses += 1
            return None
        except redis.RedisError as e:
            logger.warning("Cache GET error for key=%s: %s", key, e)
            cache_misses += 1
            return None

    def set_sync(self, key: str, value: Any) -> None:
        try:
            client = self._get_sync()
            ttl = _get_ttl(key)
            client.setex(key, ttl, json.dumps(value, default=str))
        except redis.RedisError as e:
            logger.warning("Cache SET error for key=%s: %s", key, e)

    def invalidate(self, pattern: str) -> None:
        try:
            client = self._get_sync()
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    client.delete(*keys)
                if cursor == 0:
                    break
        except redis.RedisError as e:
            logger.warning("Cache INVALIDATE error for pattern=%s: %s", pattern, e)

    def flush_all(self) -> None:
        try:
            client = self._get_sync()
            client.flushdb()
        except redis.RedisError as e:
            logger.warning("Cache FLUSH error: %s", e)

    def get_hit_rate(self) -> float:
        global cache_hits, cache_misses
        total = cache_hits + cache_misses
        if total == 0:
            return 0.0
        return round(cache_hits / total * 100, 1)

    def get_stats(self) -> dict:
        return {
            "hits": cache_hits,
            "misses": cache_misses,
            "hit_rate_pct": self.get_hit_rate(),
        }


_cache_service: RedisCacheService | None = None


def get_cache() -> RedisCacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = RedisCacheService()
    return _cache_service
