"""
Unit / integration tests for services.embedding_cache.

Round-trip and TTL tests are marked ``redis_integration`` and require a
running Redis instance at REDIS_URL (skipped automatically otherwise, same
convention as test_queue_redis.py). Redis-down / failure-handling tests use
a hand-rolled failing fake client instead of a real connection.
"""

import os
from pathlib import Path

import pytest
import redis as redis_lib
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env", override=False)

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"
_REDIS_TEST_URL = (os.environ.get("REDIS_URL") or _DEFAULT_REDIS_URL).strip() or _DEFAULT_REDIS_URL

try:
    REDIS_AVAILABLE = redis_lib.Redis.from_url(_REDIS_TEST_URL).ping()
except Exception:
    REDIS_AVAILABLE = False

import services.embedding_cache as cache_mod
from core.config import config


@pytest.fixture(autouse=True)
def _reset_cache_state(monkeypatch):
    """Point the cache at the test Redis URL and reset module client/counters."""
    monkeypatch.setattr(config, "REDIS_URL", _REDIS_TEST_URL)
    monkeypatch.setattr(cache_mod, "_redis_client", None)
    monkeypatch.setattr(cache_mod, "cache_hits", 0)
    monkeypatch.setattr(cache_mod, "cache_misses", 0)
    yield
    monkeypatch.setattr(cache_mod, "_redis_client", None)


@pytest.fixture(autouse=True)
def _clean_redis():
    if not REDIS_AVAILABLE:
        yield
        return
    conn = redis_lib.Redis.from_url(_REDIS_TEST_URL)
    conn.flushdb()
    yield
    conn.flushdb()


class _FailingRedis:
    """Stand-in Redis client whose every call raises RedisError."""

    def get(self, *args, **kwargs):
        raise redis_lib.exceptions.ConnectionError("forced failure")

    def set(self, *args, **kwargs):
        raise redis_lib.exceptions.ConnectionError("forced failure")


# ---------------------------------------------------------------------------
# Key construction
# ---------------------------------------------------------------------------

def test_cache_key_differs_by_model():
    key_a = cache_mod._cache_key("hello", provider="gemini", model="model-a", tenant_id=None)
    key_b = cache_mod._cache_key("hello", provider="gemini", model="model-b", tenant_id=None)
    assert key_a != key_b


def test_cache_key_differs_by_provider():
    key_a = cache_mod._cache_key("hello", provider="gemini", model="m", tenant_id=None)
    key_b = cache_mod._cache_key("hello", provider="openai", model="m", tenant_id=None)
    assert key_a != key_b


def test_cache_key_includes_tenant_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_CACHE_INCLUDE_TENANT", True)
    key_a = cache_mod._cache_key("hello", provider="gemini", model="m", tenant_id="tenant-a")
    key_b = cache_mod._cache_key("hello", provider="gemini", model="m", tenant_id="tenant-b")
    assert key_a != key_b


def test_cache_key_ignores_tenant_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_CACHE_INCLUDE_TENANT", False)
    key_a = cache_mod._cache_key("hello", provider="gemini", model="m", tenant_id="tenant-a")
    key_b = cache_mod._cache_key("hello", provider="gemini", model="m", tenant_id="tenant-b")
    assert key_a == key_b


def test_cache_key_namespaced_under_prefix():
    key = cache_mod._cache_key("hello", provider="gemini", model="m", tenant_id=None)
    assert key.startswith(f"{config.EMBEDDING_CACHE_KEY_PREFIX}:")


# ---------------------------------------------------------------------------
# Redis-down handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_cached_embedding_returns_none_on_redis_error(monkeypatch):
    monkeypatch.setattr(cache_mod, "_redis_client", _FailingRedis())
    result = await cache_mod.get_cached_embedding("hello", provider="gemini", model="m")
    assert result is None


@pytest.mark.asyncio
async def test_set_cached_embedding_swallows_redis_error(monkeypatch):
    monkeypatch.setattr(cache_mod, "_redis_client", _FailingRedis())
    # Must not raise.
    await cache_mod.set_cached_embedding("hello", [0.1, 0.2], provider="gemini", model="m")


# ---------------------------------------------------------------------------
# Round-trip (requires real Redis)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.redis_integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not reachable")
async def test_round_trip_returns_exact_vector():
    vector = [0.1, 0.2, 0.3, -0.4]
    await cache_mod.set_cached_embedding("hello world", vector, provider="gemini", model="m")
    result = await cache_mod.get_cached_embedding("hello world", provider="gemini", model="m")
    assert result == vector


@pytest.mark.asyncio
@pytest.mark.redis_integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not reachable")
async def test_cache_miss_returns_none_for_unseen_text():
    result = await cache_mod.get_cached_embedding("never cached", provider="gemini", model="m")
    assert result is None
