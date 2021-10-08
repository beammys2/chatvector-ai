"""Embedding service — thin facade that delegates to the configured provider."""

import logging

from core.config import config, get_embedding_dim
from services.providers import get_embedding_provider
from utils.retry import (
    DEFAULT_BACKOFF,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    retry_async,
)

logger = logging.getLogger(__name__)

# Auto-detected from the configured EMBEDDING_PROVIDER / EMBEDDING_MODEL.
# Switching provider will require re-embedding stored data.
EMBEDDING_DIM = get_embedding_dim()


async def _embed_via_provider(provider, texts: list[str]) -> list[list[float]]:
    async def _embed() -> list[list[float]]:
        logger.info("Requesting embeddings for %d inputs", len(texts))
        return await provider.embed(texts)

    return await retry_async(
        _embed,
        max_retries=DEFAULT_MAX_RETRIES,
        base_delay=DEFAULT_BASE_DELAY,
        backoff=DEFAULT_BACKOFF,
        timeout=float(config.EMBEDDING_HTTP_TIMEOUT_SEC),
        func_name="embedding_service.get_embeddings",
    )


async def get_embeddings(
    texts: list[str], *, tenant_id: str | None = None
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts.

    Delegates to whichever provider is selected via EMBEDDING_PROVIDER.
    Retry logic is applied at this service layer — providers raise on failure.

    When ``config.ENABLE_EMBEDDING_CACHE`` is false (default), this is
    byte-identical to calling the provider directly — no cache import or
    calls occur.
    """
    provider = get_embedding_provider()

    if not config.ENABLE_EMBEDDING_CACHE:
        return await _embed_via_provider(provider, texts)

    from services.embedding_cache import get_cached_embedding, set_cached_embedding

    model = provider.model_name
    results: list[list[float] | None] = [None] * len(texts)
    misses: list[tuple[int, str]] = []

    for i, text in enumerate(texts):
        cached = await get_cached_embedding(
            text, provider=config.EMBEDDING_PROVIDER, model=model, tenant_id=tenant_id
        )
        if cached is not None:
            results[i] = cached
        else:
            misses.append((i, text))

    if misses:
        miss_vectors = await _embed_via_provider(provider, [text for _, text in misses])
        for (i, text), vector in zip(misses, miss_vectors):
            results[i] = vector
            await set_cached_embedding(
                text,
                vector,
                provider=config.EMBEDDING_PROVIDER,
                model=model,
                tenant_id=tenant_id,
            )

    return results  # type: ignore[return-value]


async def get_embedding(text: str, *, tenant_id: str | None = None) -> list[float]:
    """Convenience wrapper for single-text embedding."""
    return (await get_embeddings([text], tenant_id=tenant_id))[0]


async def probe_embedding_health(text: str) -> None:
    """Single-attempt embedding probe for /status (no production retry policy)."""
    provider = get_embedding_provider()

    async def _embed() -> list[list[float]]:
        return await provider.embed([text])

    await retry_async(
        _embed,
        max_retries=0,
        base_delay=0,
        backoff=1.0,
        timeout=float(config.EMBEDDING_HEALTH_CHECK_TIMEOUT_SEC),
        func_name="embedding_service.probe_embedding_health",
    )
