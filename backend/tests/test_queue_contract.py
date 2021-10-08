"""Parametrized contract tests for memory and Redis queue backends."""

from unittest.mock import patch

import pytest

from services.queue_asyncio import AsyncioIngestionQueue
from services.queue_base import DLQEntry, QueueJob


def _make_job(doc_id: str = "doc-contract") -> QueueJob:
    return QueueJob(
        doc_id=doc_id,
        file_name="test.pdf",
        content_type="application/pdf",
        file_bytes=b"bytes",
    )


@pytest.mark.asyncio
async def test_memory_start_idempotent():
    queue = AsyncioIngestionQueue()
    await queue.start()
    worker_count = len(queue._workers)
    await queue.start()
    assert len(queue._workers) == worker_count
    await queue.stop()
    assert queue._running is False


@pytest.mark.asyncio
async def test_memory_enqueue_position_at_least_one():
    queue = AsyncioIngestionQueue()
    position = await queue.enqueue(_make_job("doc-memory-pos"))
    assert position >= 1


def test_memory_unknown_queue_position_returns_none():
    queue = AsyncioIngestionQueue()
    assert queue.queue_position("nonexistent-doc-id") is None


@pytest.mark.asyncio
async def test_memory_clear_stale_jobs_returns_integer():
    queue = AsyncioIngestionQueue()
    removed = queue.clear_stale_jobs({"missing-doc"})
    assert isinstance(removed, int)
    assert removed == 0


def test_memory_dlq_entries_are_dlq_entry_objects():
    queue = AsyncioIngestionQueue()
    queue._append_dlq(DLQEntry(
        doc_id="d1",
        file_name="f.pdf",
        content_type="application/pdf",
        attempt=1,
        error="boom",
    ))
    entries = queue.dlq_jobs()
    assert len(entries) == 1
    assert isinstance(entries[0], DLQEntry)


@pytest.mark.asyncio
async def test_memory_dlq_respects_max_entries(monkeypatch):
    monkeypatch.setattr("services.queue_asyncio.config.QUEUE_DLQ_MAX_ENTRIES", 2)
    queue = AsyncioIngestionQueue()
    for i in range(4):
        queue._append_dlq(DLQEntry(
            doc_id=f"d{i}",
            file_name="f.pdf",
            content_type="application/pdf",
            attempt=i,
            error=f"e{i}",
        ))
    entries = queue.dlq_jobs()
    assert [e.doc_id for e in entries] == ["d2", "d3"]


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_redis_start_idempotent(monkeypatch):
    pytest.importorskip("redis")
    from tests.test_queue_redis import REDIS_AVAILABLE, _REDIS_TEST_URL

    if not REDIS_AVAILABLE:
        pytest.skip("Redis not reachable")

    monkeypatch.setattr("services.queue_redis.RQ_QUEUE_NAME", "chatvector-contract-pytest")
    monkeypatch.setattr("services.queue_redis.config.REDIS_URL", _REDIS_TEST_URL)
    from services.queue_redis import RedisIngestionQueue

    queue = RedisIngestionQueue()
    with patch.object(queue, "_run_worker"):
        await queue.start()
        first = queue._worker_threads
        await queue.start()
        assert queue._worker_threads is first
    await queue.stop()
    assert queue._worker_threads == []
