import json

import pytest

from app.core.cache import RedisCacheService, _get_ttl, TTL_BY_PREFIX, DEFAULT_TTL


class TestTTL:
    def test_default_ttl(self):
        assert _get_ttl("unknown:key") == DEFAULT_TTL

    def test_rankings_ttl(self):
        assert _get_ttl("rankings:igf") == 300

    def test_calibration_ttl(self):
        assert _get_ttl("calibration:results") == 1800

    def test_simulations_ttl(self):
        assert _get_ttl("simulations:list") == 3600


class TestCacheServiceInitialization:
    def test_singleton_pattern(self):
        from app.core.cache import get_cache
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2

    def test_stats_default(self):
        service = RedisCacheService()
        stats = service.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_pct"] == 0.0

    def test_hit_rate_zero(self):
        service = RedisCacheService()
        assert service.get_hit_rate() == 0.0


@pytest.mark.skip(reason="Requires Redis running")
class TestCacheIntegration:
    def test_set_and_get(self):
        service = RedisCacheService()
        service.set_sync("test:key", {"hello": "world"})
        val = service.get_sync("test:key")
        assert val == {"hello": "world"}

    def test_invalidate(self):
        service = RedisCacheService()
        service.set_sync("test:group:a", {"data": 1})
        service.set_sync("test:group:b", {"data": 2})
        service.invalidate("test:group:*")
        assert service.get_sync("test:group:a") is None
        assert service.get_sync("test:group:b") is None

    def test_flush_all(self):
        service = RedisCacheService()
        service.set_sync("test:flush", {"data": 1})
        service.flush_all()
        assert service.get_sync("test:flush") is None
