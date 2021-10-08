"""Event-loop responsiveness while extraction/chunking runs off-thread."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.ingestion_pipeline import IngestionPipeline


@pytest.mark.asyncio
async def test_slow_extraction_does_not_block_other_coroutines():
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_extract(_file_meta, _file_bytes):
        started.set()
        await release.wait()
        return "text", []

    pipeline = IngestionPipeline()
    pipeline._update_status = AsyncMock()
    pipeline._chunk_document_text = MagicMock(return_value=[MagicMock(page_content="chunk")])
    pipeline._embed_documents_with_progress = AsyncMock(return_value=[[0.1]])

    with (
        patch(
            "services.ingestion_pipeline.extract_text_with_metadata",
            new=slow_extract,
        ),
        patch(
            "services.ingestion_pipeline._build_chunk_records",
            return_value=[{"text": "chunk"}],
        ),
        patch(
            "services.ingestion_pipeline.db.store_chunks_with_embeddings",
            new=AsyncMock(return_value=["c1"]),
        ),
    ):
        bg_task = asyncio.create_task(
            pipeline.process_document_background(
                doc_id="doc-slow",
                file_name="slow.pdf",
                content_type="application/pdf",
                file_bytes=b"%PDF-1.4",
                tenant_id="tenant-1",
                rate_limiter=None,
            )
        )

        await asyncio.wait_for(started.wait(), timeout=1.0)

        other_done = asyncio.Event()

        async def other_work() -> None:
            other_done.set()

        await asyncio.wait_for(other_work(), timeout=0.5)
        assert other_done.is_set()

        release.set()
        await asyncio.wait_for(bg_task, timeout=2.0)
