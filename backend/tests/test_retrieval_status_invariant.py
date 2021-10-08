"""Regression: retrieval excludes chunks unless Document.status == completed."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("pgvector")

from core.config import config, get_embedding_dim
from db.base import ChunkRecord
from db.sqlalchemy_service import SQLAlchemyService
from services.api_key_service import create_tenant, reset_session_factory


@pytest.fixture(autouse=True)
def _reset_api_key_session_factory():
    reset_session_factory()
    yield
    reset_session_factory()


async def _ensure_hybrid_migration(svc: SQLAlchemyService) -> None:
    """Apply 004_hybrid_retrieval.sql when content_tsv is not yet present."""
    from sqlalchemy import text

    async with svc.engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='document_chunks' "
                "AND column_name='content_tsv'"
            )
        )
        if result.scalar() == 0:
            migration_path = (
                Path(__file__).resolve().parents[1]
                / "db"
                / "init"
                / "004_hybrid_retrieval.sql"
            )
            migration_sql = migration_path.read_text(encoding="utf-8")
            async with svc.engine.begin() as migrate_conn:
                for statement in migration_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        await migrate_conn.execute(text(stmt))


async def _store_test_chunks(
    svc: SQLAlchemyService,
    doc_id: str,
    *,
    tenant_id: str,
    unique_token: str,
    embedding: list[float],
) -> None:
    await svc.store_chunks_with_embeddings(
        doc_id,
        [
            ChunkRecord(
                chunk_text=f"Intro paragraph without special terms.",
                embedding=embedding,
                chunk_index=0,
                character_offset_start=0,
                character_offset_end=40,
            ),
            ChunkRecord(
                chunk_text=f"Section referencing {unique_token} for lookup.",
                embedding=embedding,
                chunk_index=1,
                character_offset_start=41,
                character_offset_end=80,
            ),
        ],
        tenant_id=tenant_id,
    )


@pytest.mark.asyncio
async def test_failed_document_with_chunks_returns_no_vector_matches():
    """Orphan chunks on a failed document must not appear in vector retrieval."""
    if sys.platform == "win32":
        pytest.skip("Psycopg async mode not supported with ProactorEventLoop on Windows")

    dim = get_embedding_dim()
    embedding = [0.0] * dim
    embedding[0] = 1.0
    tenant_id = f"status-inv-{uuid.uuid4().hex[:8]}"
    svc = SQLAlchemyService()

    await create_tenant("Status invariant test", tenant_id=tenant_id)
    doc_id = await svc.create_document(f"failed_{uuid.uuid4()}.pdf", tenant_id=tenant_id)
    unique_token = f"STATUS-VEC-{uuid.uuid4().hex[:8]}"
    await _store_test_chunks(
        svc, doc_id, tenant_id=tenant_id, unique_token=unique_token, embedding=embedding
    )
    await svc.update_document_status(doc_id, "failed", tenant_id=tenant_id)

    matches = await svc.find_similar_chunks(
        doc_id, embedding, match_count=5, tenant_id=tenant_id
    )
    assert matches == []


@pytest.mark.asyncio
async def test_failed_document_with_chunks_returns_no_keyword_matches():
    """Orphan chunks on a failed document must not appear in keyword retrieval."""
    if sys.platform == "win32":
        pytest.skip("Psycopg async mode not supported with ProactorEventLoop on Windows")

    dim = get_embedding_dim()
    embedding = [0.0] * dim
    embedding[0] = 1.0
    tenant_id = f"status-inv-{uuid.uuid4().hex[:8]}"
    svc = SQLAlchemyService()
    await _ensure_hybrid_migration(svc)

    await create_tenant("Status invariant keyword test", tenant_id=tenant_id)
    doc_id = await svc.create_document(f"failed_{uuid.uuid4()}.pdf", tenant_id=tenant_id)
    unique_token = f"STATUS-KW-{uuid.uuid4().hex[:8]}"
    await _store_test_chunks(
        svc, doc_id, tenant_id=tenant_id, unique_token=unique_token, embedding=embedding
    )
    await svc.update_document_status(doc_id, "failed", tenant_id=tenant_id)

    with patch.object(config, "HYBRID_RETRIEVAL_ENABLED", True):
        matches = await svc.find_similar_chunks(
            doc_id,
            embedding,
            match_count=5,
            tenant_id=tenant_id,
            query_text=unique_token,
        )
    assert matches == []


@pytest.mark.asyncio
async def test_completed_document_retrieval_returns_matches():
    """Completed documents with stored chunks remain retrievable via vector and keyword."""
    if sys.platform == "win32":
        pytest.skip("Psycopg async mode not supported with ProactorEventLoop on Windows")

    dim = get_embedding_dim()
    embedding = [0.0] * dim
    embedding[0] = 1.0
    tenant_id = f"status-inv-{uuid.uuid4().hex[:8]}"
    svc = SQLAlchemyService()
    await _ensure_hybrid_migration(svc)

    await create_tenant("Status invariant completed test", tenant_id=tenant_id)
    doc_id = await svc.create_document(f"completed_{uuid.uuid4()}.pdf", tenant_id=tenant_id)
    unique_token = f"STATUS-OK-{uuid.uuid4().hex[:8]}"
    await _store_test_chunks(
        svc, doc_id, tenant_id=tenant_id, unique_token=unique_token, embedding=embedding
    )
    await svc.update_document_status(doc_id, "completed", tenant_id=tenant_id)

    vector_matches = await svc.find_similar_chunks(
        doc_id, embedding, match_count=5, tenant_id=tenant_id
    )
    assert len(vector_matches) > 0

    with patch.object(config, "HYBRID_RETRIEVAL_ENABLED", True):
        keyword_matches = await svc.find_similar_chunks(
            doc_id,
            embedding,
            match_count=5,
            tenant_id=tenant_id,
            query_text=unique_token,
        )
    assert any(unique_token in (m.chunk_text or "") for m in keyword_matches)
