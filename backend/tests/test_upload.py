from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from core.auth import AuthContext
from request_utils import make_test_request
from routes.upload import upload
from services.queue_service import QueueFull
from services.ingestion_pipeline import UploadPipelineError


@pytest.mark.asyncio
async def test_upload_route_binds_document_to_session_when_header_present():
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.filename = "test.pdf"
    mock_file.content_type = "application/pdf"
    mock_file.read = AsyncMock(return_value=b"fake-pdf-bytes")

    request = make_test_request("POST", "/upload", headers={"X-Session-Id": "sess-123"})

    mock_session = AsyncMock()
    mock_session.id = "sess-123"

    with (
        patch("routes.upload.ingestion_pipeline.validate_file", return_value=None),
        patch("routes.upload.db.create_document", new=AsyncMock(return_value="doc-1")),
        patch("routes.upload.db.update_document_status", new=AsyncMock()),
        patch("routes.upload.ingestion_queue.enqueue", new=AsyncMock(return_value=1)),
        patch(
            "routes.upload.get_or_create_session",
            new=AsyncMock(return_value=mock_session),
        ) as mock_get_session,
        patch(
            "routes.upload.register_session_document",
            new=AsyncMock(),
        ) as mock_register,
    ):
        await upload(request, mock_file, auth=AuthContext(tenant_id="tenant-123"))

    mock_get_session.assert_awaited_once_with(session_id="sess-123", tenant_id="tenant-123")
    mock_register.assert_awaited_once_with("sess-123", "doc-1", "tenant-123")


@pytest.mark.asyncio
async def test_upload_route_enqueues_job_and_returns_accepted():
    """Successful upload validates, creates a document, enqueues the job, and returns immediately."""
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.filename = "test.pdf"
    mock_file.content_type = "application/pdf"
    mock_file.read = AsyncMock(return_value=b"fake-pdf-bytes")

    with (
        patch("routes.upload.ingestion_pipeline.validate_file", return_value=None),
        patch("routes.upload.db.create_document", new=AsyncMock(return_value="doc-1")),
        patch("routes.upload.db.update_document_status", new=AsyncMock()),
        patch("routes.upload.ingestion_queue.enqueue", new=AsyncMock(return_value=1)) as mock_enqueue,
    ):
        result = await upload(make_test_request("POST", "/upload"), mock_file, auth=AuthContext(tenant_id="tenant-123"))

    assert result["message"] == "Accepted"
    assert result["document_id"] == "doc-1"
    assert result["status"] == "queued"
    assert result["queue_position"] == 1
    assert result["status_endpoint"] == "/documents/doc-1/status"
    
    enqueued_job = mock_enqueue.call_args[0][0]
    assert enqueued_job.tenant_id == "tenant-123"


@pytest.mark.asyncio
async def test_upload_route_maps_validation_error_to_http_exception():
    """A validation failure from the pipeline is surfaced as the correct HTTP error."""
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.filename = "bad.docx"
    mock_file.content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    mock_file.read = AsyncMock(return_value=b"x")

    with patch(
        "routes.upload.ingestion_pipeline.validate_file",
        side_effect=UploadPipelineError(
            status_code=400,
            code="invalid_file_type",
            stage="validation",
            message="Only PDF and TXT files are supported.",
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await upload(make_test_request("POST", "/upload"), mock_file, auth=AuthContext(tenant_id="dev"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "invalid_file_type"
    assert exc_info.value.detail["stage"] == "validation"


@pytest.mark.asyncio
async def test_upload_route_does_not_bind_session_when_enqueue_fails():
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.filename = "test.pdf"
    mock_file.content_type = "application/pdf"
    mock_file.read = AsyncMock(return_value=b"fake-pdf-bytes")

    request = make_test_request("POST", "/upload", headers={"X-Session-Id": "sess-123"})

    with (
        patch("routes.upload.ingestion_pipeline.validate_file", return_value=None),
        patch("routes.upload.db.create_document", new=AsyncMock(return_value="doc-1")),
        patch("routes.upload.db.update_document_status", new=AsyncMock()),
        patch(
            "routes.upload.ingestion_queue.enqueue",
            new=AsyncMock(side_effect=QueueFull("full")),
        ),
        patch(
            "routes.upload.get_or_create_session",
            new=AsyncMock(),
        ) as mock_get_session,
        patch(
            "routes.upload.register_session_document",
            new=AsyncMock(),
        ) as mock_register,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await upload(request, mock_file, auth=AuthContext(tenant_id="tenant-123"))

    assert exc_info.value.status_code == 503
    mock_get_session.assert_not_awaited()
    mock_register.assert_not_awaited()
