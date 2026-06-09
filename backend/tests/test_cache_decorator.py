"""Tests for the @cached decorator.

These tests verify the decorator logic without requiring Redis.
The cache calls are tested at the unit level.
"""

from unittest.mock import patch, MagicMock

from app.core.cache_decorator import cached


class TestCachedDecorator:
    def test_decorator_calls_function_on_miss(self):
        mock_fn = MagicMock(return_value={"result": "fresh"})

        with patch("app.core.cache_decorator.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.get_sync.return_value = None
            mock_get_cache.return_value = mock_cache

            decorated = cached("test:prefix")(mock_fn)
            result = decorated()

            assert result == {"result": "fresh"}
            mock_cache.get_sync.assert_called_once()
            mock_cache.set_sync.assert_called_once()

    def test_decorator_returns_cached_value(self):
        mock_fn = MagicMock(return_value={"result": "should-not-call"})

        with patch("app.core.cache_decorator.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.get_sync.return_value = {"result": "cached"}
            mock_get_cache.return_value = mock_cache

            decorated = cached("test:prefix")(mock_fn)
            result = decorated()

            assert result == {"result": "cached"}
            mock_fn.assert_not_called()
            mock_cache.set_sync.assert_not_called()
