"""Regression tests for document_chunks (document_id, chunk_index) uniqueness."""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

pytest.importorskip("pgvector")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from core.models import DocumentChunk
from core.config import get_embedding_dim
from db.base import ChunkRecord
from services.api_key_service import ensure_tenant_exists

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)


async def _unique_index_available() -> bool:
    engine = create_async_engine(DB_URL, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND indexname = 'idx_document_chunks_document_id_chunk_index'"
                )
            )
            return result.scalar_one() == 1
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def require_unique_index():
    if not asyncio.run(_unique_index_available()):
        pytest.skip(
            "Unique index idx_document_chunks_document_id_chunk_index not present; "
            "apply 011_document_chunks_unique_index.sql",
        )


@pytest.mark.asyncio
async def test_duplicate_chunk_index_replaced_on_resubmit(require_unique_index):
    """Re-storing the same chunk indices replaces rather than duplicates."""
    from db.sqlalchemy_service import SQLAlchemyService

    svc = SQLAlchemyService()
    tenant_id = f"chunk-replace-{uuid4().hex[:8]}"
    await ensure_tenant_exists(tenant_id, "Chunk replacement test")
    doc_id = await svc.create_document("replace-test.pdf", tenant_id=tenant_id)

    dim = get_embedding_dim()
    record_a = ChunkRecord(
        chunk_text="first version",
        embedding=[0.1] * dim,
        chunk_index=0,
        character_offset_start=0,
        character_offset_end=12,
    )
    record_b = ChunkRecord(
        chunk_text="replacement version",
        embedding=[0.2] * dim,
        chunk_index=0,
        character_offset_start=0,
        character_offset_end=18,
    )

    await svc.store_chunks_with_embeddings(doc_id, [record_a], tenant_id=tenant_id)
    await svc.store_chunks_with_embeddings(doc_id, [record_b], tenant_id=tenant_id)

    async with svc.async_session() as session:
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].chunk_index == 0
        assert rows[0].chunk_text == "replacement version"

    await svc.delete_document(doc_id, tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_store_chunks_twice_leaves_one_batch(require_unique_index):
    from db.sqlalchemy_service import SQLAlchemyService

    svc = SQLAlchemyService()
    tenant_id = f"chunk-batch-{uuid4().hex[:8]}"
    await ensure_tenant_exists(tenant_id, "Chunk batch test")
    doc_id = await svc.create_document("batch-test.pdf", tenant_id=tenant_id)

    dim = get_embedding_dim()
    records = [
        ChunkRecord(
            chunk_text=f"chunk {idx}",
            embedding=[0.1 * (idx + 1)] * dim,
            chunk_index=idx,
            character_offset_start=idx * 10,
            character_offset_end=(idx + 1) * 10,
        )
        for idx in range(3)
    ]

    await svc.store_chunks_with_embeddings(doc_id, records, tenant_id=tenant_id)
    await svc.store_chunks_with_embeddings(doc_id, records, tenant_id=tenant_id)

    async with svc.async_session() as session:
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 3

    await svc.delete_document(doc_id, tenant_id=tenant_id)
