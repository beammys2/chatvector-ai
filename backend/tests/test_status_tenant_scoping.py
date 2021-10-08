"""DB-backed tests for tenant-scoped /status document counts."""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

import pytest

pytest.importorskip("pgvector")

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)


async def _tables_exist() -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(DB_URL, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='documents'"
                )
            )
            return result.scalar_one() == 1
    except Exception:
        return False
    finally:
        await engine.dispose()


_requires_db = pytest.mark.skipif(
    not asyncio.get_event_loop().run_until_complete(_tables_exist())
    if sys.platform != "win32"
    else False,
    reason="documents table not available",
)


@_requires_db
@pytest.mark.asyncio
async def test_status_documents_indexed_scoped_to_tenant():
    if sys.platform == "win32":
        pytest.skip("Psycopg async mode not supported with ProactorEventLoop on Windows")

    from routes.status import _database_connected_and_document_count
    from services.api_key_service import ensure_tenant_exists
    from db.sqlalchemy_service import SQLAlchemyService

    svc = SQLAlchemyService()
    tenant_a = f"status-a-{uuid4().hex[:8]}"
    tenant_b = f"status-b-{uuid4().hex[:8]}"
    await ensure_tenant_exists(tenant_a, "Status A")
    await ensure_tenant_exists(tenant_b, "Status B")

    doc_ids_a: list[str] = []
    doc_ids_b: list[str] = []
    try:
        doc_ids_a.append(await svc.create_document("a1.pdf", tenant_id=tenant_a))
        for _ in range(4):
            doc_ids_b.append(await svc.create_document(f"b-{uuid4().hex[:4]}.pdf", tenant_id=tenant_b))

        ok_a, count_a = await _database_connected_and_document_count(tenant_a)
        ok_b, count_b = await _database_connected_and_document_count(tenant_b)

        assert ok_a is True
        assert ok_b is True
        assert count_a == 1
        assert count_b == 4
    finally:
        for doc_id in doc_ids_a:
            try:
                await svc.delete_document(doc_id, tenant_id=tenant_a)
            except Exception:
                pass
        for doc_id in doc_ids_b:
            try:
                await svc.delete_document(doc_id, tenant_id=tenant_b)
            except Exception:
                pass
        await svc.engine.dispose()
