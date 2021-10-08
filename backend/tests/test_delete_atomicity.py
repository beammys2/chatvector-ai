import pytest
import uuid

from core.config import get_embedding_dim
from db.base import ChunkRecord
from db.sqlalchemy_service import SQLAlchemyService
from services.api_key_service import create_tenant, reset_session_factory


TEST_TENANT = f"test-atomic-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _reset_api_key_session_factory():
    reset_session_factory()
    yield
    reset_session_factory()


@pytest.mark.asyncio
async def test_delete_document_atomicity_integration():
    """
    Integration test to verify that deleting a document also removes its chunks.

    Uses SQLAlchemyService directly so this always exercises the transactional
    delete path against local Postgres in CI (avoids coupling to APP_ENV after
    other tests reload core.config). Supabase deletes are covered by the RPC migration.
    """
    import sys
    if sys.platform == "win32":
        pytest.skip("Psycopg async mode not supported with ProactorEventLoop on Windows")
    pytest.importorskip("pgvector")
    dim = get_embedding_dim()
    filler = [0.1] * dim
    db = SQLAlchemyService()
    file_name = f"test_atomicity_{uuid.uuid4()}.pdf"

    await create_tenant("Atomic test tenant", tenant_id=TEST_TENANT)

    doc_id = await db.create_document(file_name, tenant_id=TEST_TENANT)

    chunk_records = [
        ChunkRecord(
            chunk_text=f"Chunk {i}",
            embedding=[0.1] * dim,
            chunk_index=i,
            page_number=1,
            character_offset_start=i * 10,
            character_offset_end=(i + 1) * 10
        )
        for i in range(3)
    ]
    await db.store_chunks_with_embeddings(doc_id, chunk_records, tenant_id=TEST_TENANT)
    await db.update_document_status(doc_id, "completed", tenant_id=TEST_TENANT)

    matches = await db.find_similar_chunks(
        doc_id, filler, match_count=10, tenant_id=TEST_TENANT
    )
    assert len(matches) == 3

    await db.delete_document(doc_id, tenant_id=TEST_TENANT)

    doc = await db.get_document(doc_id, tenant_id=TEST_TENANT)
    assert doc is None

    matches_after = await db.find_similar_chunks(
        doc_id, filler, match_count=10, tenant_id=TEST_TENANT
    )
    assert len(matches_after) == 0
