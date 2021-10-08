"""Prove mutating SDK methods do not automatically retry transport failures."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from chatvector import (
    AsyncChatVectorClient,
    BatchChatQuery,
    ChatVectorClient,
    ChatVectorTimeoutError,
)


class MutatingTransportNoRetryTests(unittest.TestCase):
    """Mutating HTTP calls must fail after exactly one transport attempt."""

    def setUp(self) -> None:
        self.client = ChatVectorClient("https://api.chatvector.test", api_key="token")

    def tearDown(self) -> None:
        self.client.close()

    def _assert_single_transport_failure(
        self,
        *,
        side_effect: list[BaseException],
        invoke,
        sleep_patch: str,
    ) -> None:
        with (
            patch.object(self.client._client, "request", side_effect=side_effect) as mock_request,
            patch(sleep_patch, return_value=None) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                invoke()

        self.assertEqual(mock_request.call_count, 1)
        mock_sleep.assert_not_called()

    def test_chat_does_not_retry_read_timeout(self) -> None:
        self._assert_single_transport_failure(
            side_effect=[httpx.ReadTimeout("timed out")],
            invoke=lambda: self.client.chat("Hello?", "doc-123"),
            sleep_patch="chatvector._retry.time.sleep",
        )

    def test_batch_chat_does_not_retry_connect_error(self) -> None:
        self._assert_single_transport_failure(
            side_effect=[httpx.ConnectError("connection refused")],
            invoke=lambda: self.client.batch_chat(
                [BatchChatQuery(question="Q?", doc_ids=["doc-123"])]
            ),
            sleep_patch="chatvector._retry.time.sleep",
        )

    def test_create_session_does_not_retry_network_error(self) -> None:
        self._assert_single_transport_failure(
            side_effect=[httpx.NetworkError("network down")],
            invoke=lambda: self.client.create_session(),
            sleep_patch="chatvector._retry.time.sleep",
        )

    def test_delete_session_does_not_retry_read_timeout(self) -> None:
        self._assert_single_transport_failure(
            side_effect=[httpx.ReadTimeout("timed out")],
            invoke=lambda: self.client.delete_session("sess-1"),
            sleep_patch="chatvector._retry.time.sleep",
        )

    def test_upload_does_not_retry_transport_error(self) -> None:
        tests_dir = Path(__file__).resolve().parent
        file_path = tests_dir / "mutating-upload-test.pdf"
        file_path.write_bytes(b"%PDF-1.4")

        try:
            with (
                patch.object(
                    self.client._client,
                    "request",
                    side_effect=[httpx.ReadTimeout("timed out")],
                ) as mock_request,
                patch("chatvector._retry.time.sleep", return_value=None) as mock_sleep,
            ):
                with self.assertRaises(ChatVectorTimeoutError):
                    self.client.upload_document(str(file_path))
        finally:
            file_path.unlink(missing_ok=True)

        self.assertEqual(mock_request.call_count, 1)
        mock_sleep.assert_not_called()

    def test_stream_chat_does_not_retry_transport_error(self) -> None:
        with (
            patch.object(
                self.client._client,
                "stream",
                side_effect=httpx.ReadTimeout("timed out"),
            ) as mock_stream,
            patch("chatvector._retry.time.sleep", return_value=None) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                list(self.client.stream_chat("Hello?", "doc-123"))

        self.assertEqual(mock_stream.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class AsyncMutatingTransportNoRetryTests(unittest.IsolatedAsyncioTestCase):
    """Async mutating HTTP calls must fail after exactly one transport attempt."""

    async def asyncSetUp(self) -> None:
        self.client = AsyncChatVectorClient("https://api.chatvector.test", api_key="token")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_chat_does_not_retry_read_timeout(self) -> None:
        with (
            patch.object(
                self.client._client,
                "request",
                side_effect=[httpx.ReadTimeout("timed out")],
            ) as mock_request,
            patch("chatvector._retry.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                await self.client.chat("Hello?", "doc-123")

        self.assertEqual(mock_request.await_count, 1)
        mock_sleep.assert_not_awaited()

    async def test_delete_session_does_not_retry_connect_error(self) -> None:
        with (
            patch.object(
                self.client._client,
                "request",
                side_effect=[httpx.ConnectError("connection refused")],
            ) as mock_request,
            patch("chatvector._retry.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                await self.client.delete_session("sess-1")

        self.assertEqual(mock_request.await_count, 1)
        mock_sleep.assert_not_awaited()
