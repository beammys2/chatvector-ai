"""Unit tests for the async ChatVector Python SDK client."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import httpx

from chatvector import (
    AsyncChatVectorClient,
    BatchChatQuery,
    BatchChatResponse,
    ChatResponse,
    ChatVectorAPIError,
    ChatVectorAuthError,
    ChatVectorRateLimitError,
    ChatVectorTimeoutError,
    DocumentResponse,
    DocumentStatus,
    Session,
    SessionListResponse,
    StreamChatEvent,
)


def make_response(
    status_code: int,
    *,
    method: str = "GET",
    url: str = "https://api.chatvector.test/test",
    json_data: object | None = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Create an ``httpx.Response`` with an attached request for testing."""
    request = httpx.Request(method, url)
    if json_data is not None:
        return httpx.Response(
            status_code=status_code,
            json=json_data,
            headers=headers,
            request=request,
        )
    return httpx.Response(
        status_code=status_code,
        text=text or "",
        headers=headers,
        request=request,
    )


def success_sse_lines() -> list[str]:
    """Return a successful token/complete/done SSE sequence."""
    return [
        "event: token",
        'data: "Hello "',
        "",
        "event: token",
        'data: "world"',
        "",
        "event: complete",
        "data: "
        + json.dumps(
            {
                "type": "complete",
                "session_id": "sess-1",
                "sources": [
                    {
                        "file_name": "guide.pdf",
                        "page_number": 1,
                        "chunk_index": 0,
                        "score": 0.91,
                        "score_type": "reranked",
                    }
                ],
                "latency_ms": 321,
                "model": "gemini-2.5-flash",
            }
        ),
        "",
        "event: done",
        "data: [DONE]",
        "",
    ]


class AsyncMockStreamResponse:
    """Async-capable streaming response double for SDK tests."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        lines: list[str] | None = None,
        json_data: object | None = None,
        text: str = "",
        close_tracker: list[bool] | None = None,
    ) -> None:
        self.status_code = status_code
        self._lines = list(lines or [])
        self._close_tracker = close_tracker
        self._json_data = json_data
        self._text = text
        self.request = httpx.Request("POST", "https://api.chatvector.test/chat/stream")

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    @property
    def text(self) -> str:
        return self._text

    def json(self) -> object:
        if self._json_data is None:
            raise ValueError("No JSON payload configured.")
        return self._json_data

    def close(self) -> None:
        if self._close_tracker is not None:
            self._close_tracker.append(True)

    async def aclose(self) -> None:
        self.close()


class AsyncMockStreamContext:
    """Async context manager wrapper around ``AsyncMockStreamResponse``."""

    def __init__(self, response: AsyncMockStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> AsyncMockStreamResponse:
        return self._response

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        await self._response.aclose()


class AsyncChatVectorClientTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the async ChatVector client against mocked HTTPX calls."""

    async def asyncSetUp(self) -> None:
        self.client = AsyncChatVectorClient("https://api.chatvector.test", api_key="token")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_upload_document_returns_document_response_and_falls_back_to_upload(self) -> None:
        tests_dir = Path(__file__).resolve().parent
        file_path = tests_dir / "guide-test-upload.pdf"
        file_path.write_bytes(b"%PDF-1.4")

        ingest_not_found = make_response(
            404,
            method="POST",
            url="https://api.chatvector.test/ingest",
            json_data={"detail": {"message": "Not found"}},
        )
        upload_ok = make_response(
            202,
            method="POST",
            url="https://api.chatvector.test/upload",
            json_data={
                "message": "Accepted",
                "document_id": "doc-123",
                "status": "queued",
                "queue_position": 1,
                "status_endpoint": "/documents/doc-123/status",
            },
        )

        try:
            with patch.object(
                self.client._client,
                "request",
                new=AsyncMock(side_effect=[ingest_not_found, upload_ok]),
            ) as mock_request:
                response = await self.client.upload_document(str(file_path))
        finally:
            file_path.unlink(missing_ok=True)

        self.assertIsInstance(response, DocumentResponse)
        self.assertEqual(response.document_id, "doc-123")
        self.assertEqual(mock_request.await_count, 2)

    async def test_get_status_returns_document_status_model(self) -> None:
        response = make_response(
            200,
            url="https://api.chatvector.test/documents/doc-123/status",
            json_data={
                "document_id": "doc-123",
                "status": "embedding",
                "chunks": {"total": 10, "processed": 4},
                "queue_position": 2,
            },
        )

        with patch.object(
            self.client._client,
            "request",
            new=AsyncMock(return_value=response),
        ):
            status = await self.client.get_status("doc-123")

        self.assertIsInstance(status, DocumentStatus)
        self.assertEqual(status.status, "embedding")

    async def test_chat_returns_typed_response_with_sources(self) -> None:
        response = make_response(
            200,
            method="POST",
            url="https://api.chatvector.test/chat",
            json_data={
                "question": "What is this document about?",
                "chunks": 2,
                "answer": "It is an onboarding guide.",
                "sources": [
                    {
                        "file_name": "guide.pdf",
                        "page_number": 1,
                        "chunk_index": 0,
                        "score": 0.95,
                        "score_type": "vector",
                    }
                ],
            },
        )

        with patch.object(
            self.client._client,
            "request",
            new=AsyncMock(return_value=response),
        ):
            result = await self.client.chat("What is this document about?", "doc-123", match_count=2)

        self.assertIsInstance(result, ChatResponse)
        self.assertEqual(result.answer, "It is an onboarding guide.")

    async def test_batch_chat_returns_typed_batch_response(self) -> None:
        response = make_response(
            200,
            method="POST",
            url="https://api.chatvector.test/chat/batch",
            json_data={
                "count": 1,
                "success_count": 1,
                "failure_count": 0,
                "results": [
                    {
                        "status": "ok",
                        "question": "Summarize it.",
                        "doc_ids": ["doc-123"],
                        "chunks": 3,
                        "answer": "Summary",
                        "sources": [],
                    }
                ],
            },
        )

        with patch.object(
            self.client._client,
            "request",
            new=AsyncMock(return_value=response),
        ):
            batch = await self.client.batch_chat(
                [BatchChatQuery(question="Summarize it.", doc_ids=["doc-123"], match_count=3)]
            )

        self.assertIsInstance(batch, BatchChatResponse)
        self.assertEqual(batch.results[0].answer, "Summary")

    async def test_wait_for_ready_polls_until_document_is_completed(self) -> None:
        queued = DocumentStatus(document_id="doc-123", status="queued")
        completed = DocumentStatus(document_id="doc-123", status="completed")

        with (
            patch.object(
                self.client,
                "get_status",
                new=AsyncMock(side_effect=[queued, completed]),
            ) as mock_status,
            patch("chatvector._retry.asyncio.sleep", new=AsyncMock(return_value=None)),
        ):
            result = await self.client.wait_for_ready("doc-123", timeout=10, interval=1)

        self.assertEqual(result.status, "completed")
        self.assertEqual(mock_status.await_count, 2)

    async def test_auth_failures_raise_chatvector_auth_error(self) -> None:
        response = make_response(
            401,
            method="POST",
            url="https://api.chatvector.test/chat",
            json_data={"detail": {"code": "unauthorized", "message": "Unauthorized"}},
        )

        with patch.object(
            self.client._client,
            "request",
            new=AsyncMock(return_value=response),
        ):
            with self.assertRaises(ChatVectorAuthError):
                await self.client.chat("Hello?", "doc-123")

    async def test_rate_limit_failures_raise_chatvector_rate_limit_error(self) -> None:
        responses = [
            make_response(
                429,
                url="https://api.chatvector.test/documents/doc-123/status",
                json_data={"detail": {"code": "rate_limited", "message": "Slow down"}},
                headers={"Retry-After": "0"},
            )
            for _ in range(3)
        ]

        with (
            patch.object(
                self.client._client,
                "request",
                new=AsyncMock(side_effect=responses),
            ) as mock_request,
            patch("chatvector._retry.asyncio.sleep", new=AsyncMock(return_value=None)) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorRateLimitError):
                await self.client.get_status("doc-123")

        self.assertEqual(mock_request.await_count, 3)
        self.assertEqual(mock_sleep.await_count, 2)

    async def test_timeout_failures_raise_chatvector_timeout_error(self) -> None:
        timeouts = [httpx.ReadTimeout("timed out") for _ in range(3)]

        with (
            patch.object(
                self.client._client,
                "request",
                new=AsyncMock(side_effect=timeouts),
            ) as mock_request,
            patch("chatvector._retry.asyncio.sleep", new=AsyncMock(return_value=None)) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                await self.client.get_status("doc-123")

        self.assertEqual(mock_request.await_count, 3)
        self.assertEqual(mock_sleep.await_count, 2)

    async def test_create_session_returns_typed_session(self) -> None:
        response = make_response(
            201,
            method="POST",
            url="https://api.chatvector.test/sessions",
            json_data={
                "id": "sess-1",
                "tenant_id": "tenant-1",
                "created_at": "2026-01-01T00:00:00",
                "last_active": "2026-01-01T00:00:00",
                "metadata": {},
                "document_ids": [],
            },
        )

        with patch.object(
            self.client._client,
            "request",
            new=AsyncMock(return_value=response),
        ) as mock_request:
            session = await self.client.create_session()

        self.assertIsInstance(session, Session)
        self.assertEqual(session.id, "sess-1")
        self.assertEqual(mock_request.await_args.kwargs["json"], {})

    async def test_list_sessions_returns_typed_list_response(self) -> None:
        response = make_response(
            200,
            url="https://api.chatvector.test/sessions",
            json_data={
                "sessions": [
                    {
                        "id": "sess-1",
                        "tenant_id": "tenant-1",
                        "created_at": "2026-01-01T00:00:00",
                        "last_active": "2026-01-01T00:00:00",
                        "metadata": {},
                        "document_ids": [],
                    }
                ]
            },
        )

        with patch.object(
            self.client._client,
            "request",
            new=AsyncMock(return_value=response),
        ):
            result = await self.client.list_sessions()

        self.assertIsInstance(result, SessionListResponse)
        self.assertEqual(len(result.sessions), 1)

    async def test_delete_session_sends_delete_request(self) -> None:
        response = make_response(
            204,
            method="DELETE",
            url="https://api.chatvector.test/sessions/sess-1",
        )

        with patch.object(
            self.client._client,
            "request",
            new=AsyncMock(return_value=response),
        ) as mock_request:
            await self.client.delete_session("sess-1")

        self.assertEqual(mock_request.await_args.args[:2], ("DELETE", "sessions/sess-1"))

    async def test_stream_chat_yields_events_from_mocked_response(self) -> None:
        mock_response = AsyncMockStreamResponse(lines=success_sse_lines())

        with patch.object(
            self.client._client,
            "stream",
            return_value=AsyncMockStreamContext(mock_response),
        ):
            events = [
                event
                async for event in self.client.stream_chat(
                    "Summarize this", "doc-123", session_id="sess-1"
                )
            ]

        self.assertEqual(len(events), 3)
        self.assertIsInstance(events[0], StreamChatEvent)
        self.assertEqual(events[2].sources[0].score, 0.91)

    async def test_stream_chat_raises_on_error_event(self) -> None:
        lines = [
            "event: error",
            "data: "
            + json.dumps(
                {
                    "type": "error",
                    "code": "no_documents_in_scope",
                    "message": "No documents available.",
                }
            ),
            "",
        ]
        mock_response = AsyncMockStreamResponse(lines=lines)

        with patch.object(
            self.client._client,
            "stream",
            return_value=AsyncMockStreamContext(mock_response),
        ):
            with self.assertRaises(ChatVectorAPIError) as exc_info:
                async for _ in self.client.stream_chat("Question?", "doc-123"):
                    pass

        self.assertEqual(exc_info.exception.details["code"], "no_documents_in_scope")

    async def test_async_context_manager_closes_client(self) -> None:
        client = AsyncChatVectorClient("https://api.chatvector.test")
        with patch.object(client._client, "aclose", new=AsyncMock()) as mock_aclose:
            async with client:
                self.assertIsInstance(client, AsyncChatVectorClient)
            mock_aclose.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
