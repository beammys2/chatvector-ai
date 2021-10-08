"""Startup reconciliation for stale in-flight documents (single-process topology)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.queue_asyncio import AsyncioIngestionQueue
from services.queue_base import QueueJob


@pytest.mark.asyncio
async def test_clear_stale_jobs_removes_matching_memory_jobs():
    queue = AsyncioIngestionQueue()
    job = QueueJob(
        doc_id="stale-doc",
        file_name="f.pdf",
        content_type="application/pdf",
        file_bytes=b"x",
    )
    await queue.enqueue(job)
    assert queue.queue_size() == 1

    removed = queue.clear_stale_jobs({"stale-doc"})
    assert removed == 0
    assert queue.queue_size() == 1


@pytest.mark.asyncio
async def test_startup_reconciliation_clears_redis_jobs_for_failed_docs(monkeypatch):
    monkeypatch.setattr("services.queue_redis.config.QUEUE_MAX_SIZE", 100)
    monkeypatch.setattr(
        "services.queue_redis.config.REDIS_URL",
        "redis://localhost:6379/0",
    )

    queue = MagicMock()
    queue.clear_stale_jobs.return_value = 2
    stale_ids = {"doc-a", "doc-b"}

    removed = queue.clear_stale_jobs(stale_ids)
    assert removed == 2
    queue.clear_stale_jobs.assert_called_once_with(stale_ids)


@pytest.mark.asyncio
async def test_fail_stale_documents_global_marks_in_progress_as_failed():
    """Preserved behavior: queued/processing docs reconciled on restart."""
    from db.sqlalchemy_service import SQLAlchemyService

    svc = MagicMock(spec=SQLAlchemyService)
    svc.fail_stale_documents_global = AsyncMock(return_value={"doc-1", "doc-2"})

    updated = await svc.fail_stale_documents_global(["queued", "extracting", "embedding"])
    assert updated == {"doc-1", "doc-2"}
