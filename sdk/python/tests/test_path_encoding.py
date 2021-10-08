"""Tests for URL path component encoding in the Python SDK."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from chatvector import ChatVectorClient
from chatvector._common import encode_path_component


class PathEncodingTests(unittest.TestCase):
    """Dynamic path segments must be encoded like TypeScript encodeURIComponent."""

    def setUp(self) -> None:
        self.client = ChatVectorClient("https://api.chatvector.test", api_key="token")

    def tearDown(self) -> None:
        self.client.close()

    def test_encode_path_component_matches_typescript_semantics(self) -> None:
        cases = {
            "proj/run-1": "proj%2Frun-1",
            "a b": "a%20b",
            "q?mark": "q%3Fmark",
            "hash#tag": "hash%23tag",
            "percent%25": "percent%2525",
            "café": "caf%C3%A9",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(encode_path_component(raw), expected)

    def test_get_session_encodes_slash_in_session_id(self) -> None:
        response = make_response(
            200,
            url="https://api.chatvector.test/sessions/proj%2Frun-1",
            json_data={
                "id": "proj/run-1",
                "tenant_id": "tenant-1",
                "created_at": "2026-01-01T00:00:00",
                "last_active": "2026-01-01T00:00:00",
                "metadata": {},
                "document_ids": [],
            },
        )

        with patch.object(self.client._client, "request", return_value=response) as mock_request:
            session = self.client.get_session("proj/run-1")

        self.assertEqual(session.id, "proj/run-1")
        self.assertEqual(mock_request.call_args.args[1], "sessions/proj%2Frun-1")

    def test_get_session_history_encodes_session_id(self) -> None:
        response = make_response(
            200,
            url="https://api.chatvector.test/sessions/proj%2Frun-1/history",
            json_data={"messages": []},
        )

        with patch.object(self.client._client, "request", return_value=response) as mock_request:
            history = self.client.get_session_history("proj/run-1")

        self.assertEqual(history.messages, [])
        self.assertEqual(mock_request.call_args.args[1], "sessions/proj%2Frun-1/history")

    def test_get_status_encodes_document_id(self) -> None:
        response = make_response(
            200,
            url="https://api.chatvector.test/documents/doc%2F123/status",
            json_data={"document_id": "doc/123", "status": "queued"},
        )

        with patch.object(self.client._client, "request", return_value=response) as mock_request:
            status = self.client.get_status("doc/123")

        self.assertEqual(status.document_id, "doc/123")
        self.assertEqual(mock_request.call_args.args[1], "documents/doc%2F123/status")

    def test_delete_document_encodes_document_id(self) -> None:
        response = make_response(
            204,
            method="DELETE",
            url="https://api.chatvector.test/documents/doc%2F123",
        )

        with patch.object(self.client._client, "request", return_value=response) as mock_request:
            self.client.delete_document("doc/123")

        self.assertEqual(mock_request.call_args.args[:2], ("DELETE", "documents/doc%2F123"))


def make_response(
    status_code: int,
    *,
    method: str = "GET",
    url: str = "https://api.chatvector.test/test",
    json_data: object | None = None,
) -> httpx.Response:
    request = httpx.Request(method, url)
    if json_data is not None:
        return httpx.Response(status_code=status_code, json=json_data, request=request)
    return httpx.Response(status_code=status_code, request=request)


if __name__ == "__main__":
    unittest.main()
