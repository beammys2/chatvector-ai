"""Regression: chunk store retry converges after a prior successful store."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.ingestion_pipeline import IngestionPipeline
from tests.test_ingestion_pipeline import _SingleChunkSplitter


@pytest.mark.asyncio
async def test_process_document_background_retry_after_store_succeeds():
    """Simulated queue retry re-stores chunks without IntegrityError."""
    pipeline = IngestionPipeline(splitter_cls=_SingleChunkSplitter)
    store_calls = 0
    doc_id = "doc-retry-converge"

    async def counting_store(doc_id_arg, chunk_records, tenant_id):
        nonlocal store_calls
        store_calls += 1
        return [f"chunk-{store_calls}"]

    with patch("services.ingestion_pipeline.db.update_document_status", new=AsyncMock()), patch(
        "services.ingestion_pipeline.db.store_chunks_with_embeddings",
        side_effect=counting_store,
    ), patch(
        "services.ingestion_pipeline.extract_text_with_metadata",
        new=AsyncMock(return_value=("hello world", [])),
    ), patch(
        "services.ingestion_pipeline.get_embeddings",
        new=AsyncMock(return_value=[[0.1, 0.2]]),
    ):
        job_kwargs = dict(
            doc_id=doc_id,
            file_name="test.pdf",
            content_type="application/pdf",
            file_bytes=b"%PDF-fake",
            tenant_id="dev",
        )
        await pipeline.process_document_background(**job_kwargs)
        await pipeline.process_document_background(**job_kwargs)

    assert store_calls == 2


@pytest.mark.asyncio
async def test_process_document_background_completed_failure_then_retry_store_succeeds():
    """Store commits; completed update fails; a later store call still succeeds."""
    pipeline = IngestionPipeline(splitter_cls=_SingleChunkSplitter)
    doc_id = "doc-status-fail-retry"
    completed_attempts = 0

    async def flaky_update(*, doc_id, status, tenant_id, error=None, chunks=None):
        nonlocal completed_attempts
        if status == "completed":
            completed_attempts += 1
            if completed_attempts == 1:
                raise RuntimeError("status write failed")

    with patch(
        "services.ingestion_pipeline.db.update_document_status",
        side_effect=flaky_update,
    ), patch(
        "services.ingestion_pipeline.db.delete_document_chunks",
        new=AsyncMock(side_effect=RuntimeError("cleanup failed")),
    ), patch(
        "services.ingestion_pipeline.db.store_chunks_with_embeddings",
        new=AsyncMock(return_value=["chunk-1"]),
    ) as mock_store, patch(
        "services.ingestion_pipeline.extract_text_with_metadata",
        new=AsyncMock(return_value=("hello world", [])),
    ), patch(
        "services.ingestion_pipeline.get_embeddings",
        new=AsyncMock(return_value=[[0.1, 0.2]]),
    ):
        job_kwargs = dict(
            doc_id=doc_id,
            file_name="test.pdf",
            content_type="application/pdf",
            file_bytes=b"%PDF-fake",
            tenant_id="dev",
        )

        with pytest.raises(RuntimeError, match="status write failed"):
            await pipeline.process_document_background(**job_kwargs)

        await pipeline.process_document_background(**job_kwargs)

    assert mock_store.await_count == 2
    assert completed_attempts == 2
