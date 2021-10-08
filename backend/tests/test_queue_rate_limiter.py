"""Tests for embedding rate limiter semantics and cross-thread safety."""

import asyncio
import threading
from unittest.mock import AsyncMock, patch

import pytest

from services.queue_asyncio import AsyncioIngestionQueue
from services.queue_base import (
    TokenBucketRateLimiter,
    get_process_embedding_rate_limiter,
    reset_process_embedding_rate_limiter,
)


@pytest.fixture(autouse=True)
def _reset_process_limiter():
    reset_process_embedding_rate_limiter()
    yield
    reset_process_embedding_rate_limiter()


@pytest.mark.asyncio
async def test_thirty_chunks_at_batch_ten_causes_three_acquisitions(monkeypatch):
    monkeypatch.setattr("services.ingestion_pipeline._EMBEDDING_PROGRESS_BATCH_SIZE", 10)
    acquire_calls = []

    class CountingLimiter:
        async def acquire(self) -> None:
            acquire_calls.append(1)

    limiter = CountingLimiter()
    langchain_docs = [
        type("Doc", (), {"page_content": f"chunk-{i}"})()
        for i in range(30)
    ]

    with patch(
        "services.ingestion_pipeline.get_embeddings",
        new=AsyncMock(return_value=[[0.1]] * 10),
    ):
        from services.ingestion_pipeline import IngestionPipeline

        pipeline = IngestionPipeline()
        pipeline._update_status = AsyncMock()
        await pipeline._embed_documents_with_progress(
            doc_id="doc-1",
            tenant_id="tenant-1",
            langchain_docs=langchain_docs,
            rate_limiter=limiter,
        )

    assert len(acquire_calls) == 3


def test_two_redis_jobs_share_process_limiter(monkeypatch):
    monkeypatch.setattr("core.config.config.QUEUE_EMBEDDING_RPS", 5.0)
    reset_process_embedding_rate_limiter()
    first = get_process_embedding_rate_limiter()
    second = get_process_embedding_rate_limiter()
    assert first is second


@pytest.mark.asyncio
async def test_limiter_usable_from_two_threads_with_separate_loops():
    limiter = TokenBucketRateLimiter(rate=100.0, capacity=100.0)
    errors: list[Exception] = []

    def run_in_thread() -> None:
        try:
            asyncio.run(limiter.acquire())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run_in_thread) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert errors == []


@pytest.mark.asyncio
async def test_memory_queue_workers_share_one_limiter():
    queue = AsyncioIngestionQueue()
    assert queue._rate_limiter._lock.__class__.__name__ == "lock"
    limiter_id = id(queue._rate_limiter)
    await queue.start()
    try:
        assert id(queue._rate_limiter) == limiter_id
    finally:
        await queue.stop()
