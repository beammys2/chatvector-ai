"""Tests for document error field lifecycle during status transitions."""

from uuid import uuid4

import pytest

pytest.importorskip("pgvector")

from db.sqlalchemy_service import SQLAlchemyService
from services.api_key_service import ensure_tenant_exists


@pytest.fixture
async def test_tenant_id():
    tenant_id = f"doc-error-{uuid4().hex[:8]}"
    await ensure_tenant_exists(tenant_id, "Document error state test")
    return tenant_id


@pytest.mark.asyncio
async def test_update_document_status_clears_error_on_non_failed(test_tenant_id):
    svc = SQLAlchemyService()
    tenant_id = test_tenant_id
    doc_id = await svc.create_document("error-clear.pdf", tenant_id=tenant_id)

    await svc.update_document_status(
        doc_id=doc_id,
        status="failed",
        tenant_id=tenant_id,
        error={"stage": "embedding", "message": "temporary failure"},
    )

    status = await svc.get_document_status(doc_id, tenant_id=tenant_id)
    assert status is not None
    assert status["error"] is not None

    await svc.update_document_status(
        doc_id=doc_id,
        status="retrying",
        tenant_id=tenant_id,
    )

    status = await svc.get_document_status(doc_id, tenant_id=tenant_id)
    assert status is not None
    assert status["status"] == "retrying"
    assert status.get("error") is None

    await svc.delete_document(doc_id, tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_update_document_status_preserves_error_when_failed(test_tenant_id):
    svc = SQLAlchemyService()
    tenant_id = test_tenant_id
    doc_id = await svc.create_document("error-keep.pdf", tenant_id=tenant_id)
    error = {"stage": "storing", "message": "still broken"}

    await svc.update_document_status(
        doc_id=doc_id,
        status="failed",
        tenant_id=tenant_id,
        error=error,
    )

    await svc.update_document_status(
        doc_id=doc_id,
        status="failed",
        tenant_id=tenant_id,
    )

    status = await svc.get_document_status(doc_id, tenant_id=tenant_id)
    assert status is not None
    assert status["error"] == error

    await svc.delete_document(doc_id, tenant_id=tenant_id)
