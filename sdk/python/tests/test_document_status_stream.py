"""Unit tests for document status streaming in the ChatVector Python SDK."""

from __future__ import annotations

import json
import unittest
from typing import Iterator
from unittest.mock import patch

import httpx

from chatvector import (
    ChatVectorAPIError,
    ChatVectorClient,
    ChatVectorTimeoutError,
    DocumentStatus,
)
from chatvector._sse import iter_document_status_events, map_document_status_stream_error


class MockStreamResponse:
    """Minimal streaming response double for SDK tests."""

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
        self.request = httpx.Request(
            "GET",
            "https://api.chatvector.test/documents/doc-123/status/stream",
        )

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def iter_lines(self) -> Iterator[str]:
        yield from self._lines

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


class MockStreamContext:
    """Context manager wrapper around ``MockStreamResponse``."""

    def __init__(self, response: MockStreamResponse) -> None:
        self._response = response

    def __enter__(self) -> MockStreamResponse:
        return self._response

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self._response.close()


def status_sse_lines() -> list[str]:
    """Return a representative queued -> extracting -> completed SSE sequence."""
    return [
        "event: status",
        "data: "
        + json.dumps(
            {
                "document_id": "doc-123",
                "status": "queued",
                "queue_position": 2,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:01Z",
            }
        ),
        "",
        "event: status",
        "data: "
        + json.dumps(
            {
                "document_id": "doc-123",
                "status": "extracting",
                "chunks": {"total": 10, "processed": 0},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:05Z",
            }
        ),
        "",
        "event: status",
        "data: "
        + json.dumps(
            {
                "document_id": "doc-123",
                "status": "completed",
                "chunks": {"total": 10, "processed": 10},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:30Z",
            }
        ),
        "",
    ]


class DocumentStatusStreamTests(unittest.TestCase):
    """Exercise document status SSE parsing and client iteration."""

    def setUp(self) -> None:
        self.client = ChatVectorClient("https://api.chatvector.test", api_key="token")
        self.addCleanup(self.client.close)

    def test_iter_document_status_events_parses_status_snapshots(self) -> None:
        """SSE parsing should yield typed document status snapshots."""
        events = list(
            iter_document_status_events(
                iter(status_sse_lines()),
                map_error=map_document_status_stream_error,
            )
        )

        self.assertEqual(len(events), 3)
        self.assertIsInstance(events[0], DocumentStatus)
        self.assertEqual(events[0].status, "queued")
        self.assertEqual(events[0].queue_position, 2)
        self.assertEqual(events[1].status, "extracting")
        self.assertEqual(events[1].chunks, {"total": 10, "processed": 0})
        self.assertEqual(events[2].status, "completed")
        self.assertEqual(events[2].chunks, {"total": 10, "processed": 10})

    def test_map_document_status_stream_error_timeout(self) -> None:
        """Stream timeout errors should map to ChatVectorTimeoutError."""
        exc = map_document_status_stream_error(
            {"message": "Timed out waiting for status."}
        )
        self.assertIsInstance(exc, ChatVectorTimeoutError)

    def test_iter_document_status_events_raises_on_error_event(self) -> None:
        """Backend error events should become structured SDK exceptions."""
        lines = [
            "event: error",
            "data: " + json.dumps({"message": "Document not found."}),
            "",
        ]

        with self.assertRaises(ChatVectorAPIError) as exc_info:
            list(
                iter_document_status_events(
                    iter(lines),
                    map_error=map_document_status_stream_error,
                )
            )

        self.assertIn("Document not found.", str(exc_info.exception))

    def test_iter_document_status_yields_events_from_mocked_response(self) -> None:
        """The client should expose a typed iterator over status SSE events."""
        mock_response = MockStreamResponse(lines=status_sse_lines())

        with patch.object(
            self.client._client,
            "stream",
            return_value=MockStreamContext(mock_response),
        ):
            events = list(self.client.iter_document_status("doc-123"))

        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1].status, "completed")

    def test_iter_document_status_forwards_timeout(self) -> None:
        """Status streaming requests should forward optional timeout overrides."""
        mock_response = MockStreamResponse(lines=status_sse_lines())
        captured: dict[str, object] = {}

        def capture_stream(method: str, url: str, **kwargs: object) -> MockStreamContext:
            captured["method"] = method
            captured["url"] = url
            captured["kwargs"] = kwargs
            return MockStreamContext(mock_response)

        with patch.object(self.client._client, "stream", side_effect=capture_stream):
            list(self.client.iter_document_status("doc-123", timeout=45.0))

        self.assertEqual(captured["method"], "GET")
        self.assertEqual(captured["url"], "documents/doc-123/status/stream")
        self.assertEqual(captured["kwargs"], {"timeout": 45.0})

    def test_iter_document_status_raises_on_http_error(self) -> None:
        """Non-success HTTP responses should map to SDK exceptions before parsing."""
        mock_response = MockStreamResponse(
            status_code=400,
            json_data={
                "detail": {
                    "code": "streaming_disabled",
                    "message": "Streaming responses are currently disabled.",
                }
            },
            text='{"detail":{"code":"streaming_disabled","message":"Streaming responses are currently disabled."}}',
        )

        with patch.object(
            self.client._client,
            "stream",
            return_value=MockStreamContext(mock_response),
        ):
            with self.assertRaises(ChatVectorAPIError) as exc_info:
                list(self.client.iter_document_status("doc-123"))

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertIn("Streaming responses are currently disabled.", str(exc_info.exception))

    def test_iter_document_status_early_termination_closes_response(self) -> None:
        """Stopping iteration early should close the underlying HTTP stream."""
        close_tracker: list[bool] = []
        mock_response = MockStreamResponse(
            lines=status_sse_lines(),
            close_tracker=close_tracker,
        )

        with patch.object(
            self.client._client,
            "stream",
            return_value=MockStreamContext(mock_response),
        ):
            iterator = self.client.iter_document_status("doc-123")
            next(iterator)
            iterator.close()

        self.assertTrue(close_tracker)

    def test_iter_document_status_timeout_raises_timeout_error(self) -> None:
        """Transport timeouts should map to ChatVectorTimeoutError."""
        with patch.object(
            self.client._client,
            "stream",
            side_effect=httpx.ReadTimeout("timed out"),
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                list(self.client.iter_document_status("doc-123"))


if __name__ == "__main__":
    unittest.main()
