"""Optional Redis-backed cache for embedding results.

Disabled by default (``ENABLE_EMBEDDING_CACHE=false``). When enabled, caches
vectors keyed by ``(provider, model, text[, tenant_id])`` so repeated inputs
skip the embedding provider call. Any Redis failure is swallowed — the cache
must never fail a request; callers fall back to calling the provider.
"""

import asyncio
import logging

import orjson
import redis as redis_lib
import xxhash

from core.config import config, redis_connection_kwargs

logger = logging.getLogger(__name__)

_redis_client: redis_lib.Redis | None = None

# Process-local hit/miss counters — not aggregated across processes.
cache_hits = 0
cache_misses = 0


def _get_client() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.Redis.from_url(
            config.REDIS_URL, **redis_connection_kwargs()
        )
    return _redis_client


def _cache_key(text: str, *, provider: str, model: str, tenant_id: str | None) -> str:
    parts = [provider, model, text]
    if config.EMBEDDING_CACHE_INCLUDE_TENANT and tenant_id:
        parts = [tenant_id] + parts
    raw = "\x00".join(parts).encode("utf-8")
    digest = xxhash.xxh64(raw).hexdigest()
    return f"{config.EMBEDDING_CACHE_KEY_PREFIX}:{digest}"


def _sync_get(key: str) -> list[float] | None:
    raw = _get_client().get(key)
    if raw is None:
        return None
    return orjson.loads(raw)


def _sync_set(key: str, embedding: list[float]) -> None:
    payload = orjson.dumps(embedding)
    ttl = config.EMBEDDING_CACHE_TTL_SECONDS or None
    _get_client().set(key, payload, ex=ttl)


async def get_cached_embedding(
    text: str, *, provider: str, model: str, tenant_id: str | None = None
) -> list[float] | None:
    global cache_hits, cache_misses
    key = _cache_key(text, provider=provider, model=model, tenant_id=tenant_id)
    try:
        result = await asyncio.to_thread(_sync_get, key)
    except redis_lib.exceptions.RedisError as exc:
        logger.warning("Embedding cache GET failed, bypassing cache: %s", exc)
        return None

    if result is not None:
        cache_hits += 1
        logger.info(
            "Embedding cache hit",
            extra={"cache_result": "hit", "provider": provider, "model": model},
        )
    else:
        cache_misses += 1
        logger.info(
            "Embedding cache miss",
            extra={"cache_result": "miss", "provider": provider, "model": model},
        )
    return result


async def set_cached_embedding(
    text: str,
    embedding: list[float],
    *,
    provider: str,
    model: str,
    tenant_id: str | None = None,
) -> None:
    key = _cache_key(text, provider=provider, model=model, tenant_id=tenant_id)
    try:
        await asyncio.to_thread(_sync_set, key, embedding)
    except redis_lib.exceptions.RedisError as exc:
        logger.warning("Embedding cache SET failed, bypassing cache: %s", exc)
