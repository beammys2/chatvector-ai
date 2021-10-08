"""Tests for wait_for_ready wall-clock deadline semantics."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from chatvector import (
    AsyncChatVectorClient,
    ChatVectorClient,
    ChatVectorTimeoutError,
    DocumentStatus,
)
from chatvector._retry import RetryDeadlineExceeded, WantsRetry, retry_sync


class WaitForReadyDeadlineSyncTests(unittest.TestCase):
    """Sync wait_for_ready must not exceed its overall timeout budget."""

    def setUp(self) -> None:
        self.client = ChatVectorClient("https://api.chatvector.test", api_key="token")

    def tearDown(self) -> None:
        self.client.close()

    def test_polling_sleep_is_capped_by_remaining_time(self) -> None:
        """The interval between polls must not exceed the remaining deadline."""
        pending = DocumentStatus(document_id="doc-123", status="queued")
        monotonic_values = iter([0.0, 8.0, 8.0, 8.0, 8.0, 10.0, 10.0, 10.0])

        with (
            patch.object(self.client, "get_status", return_value=pending),
            patch("chatvector.client.time.monotonic", side_effect=monotonic_values),
            patch("chatvector.client.time.sleep", return_value=None) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                self.client.wait_for_ready("doc-123", timeout=10, interval=5)

        mock_sleep.assert_called_once_with(2.0)

    def test_retry_helper_raises_when_deadline_elapses_before_retry(self) -> None:
        """Shared retry logic must stop before sleeping past the deadline."""
        calls = [0]

        def func() -> None:
            calls[0] += 1
            raise WantsRetry(5.0)

        with (
            patch("chatvector._retry.time.monotonic", side_effect=[0.0, 0.0, 1.1]),
            patch("chatvector._retry.time.sleep", return_value=None) as mock_sleep,
            patch("chatvector._retry.random.uniform", return_value=0.0),
        ):
            with self.assertRaises(RetryDeadlineExceeded):
                retry_sync(func, max_retries=2, base_delay=0.5, deadline_monotonic=1.0)

        self.assertEqual(calls[0], 1)
        mock_sleep.assert_not_called()

    def test_get_status_503_does_not_retry_past_wait_deadline(self) -> None:
        """Transient GET failures during polling must honor the wait deadline."""
        response = make_response(
            503,
            url="https://api.chatvector.test/documents/doc-123/status",
            json_data={"detail": {"message": "Busy"}},
            headers={"Retry-After": "30"},
        )
        call_count = [0]

        def fake_monotonic() -> float:
            call_count[0] += 1
            return 0.0 if call_count[0] <= 8 else 1.5

        with (
            patch.object(self.client._client, "request", return_value=response) as mock_request,
            patch("chatvector.client.time.monotonic", side_effect=fake_monotonic),
            patch("chatvector._common.time.monotonic", side_effect=fake_monotonic),
            patch("chatvector._retry.time.monotonic", side_effect=fake_monotonic),
            patch("chatvector._retry.time.sleep", return_value=None) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                self.client.wait_for_ready("doc-123", timeout=1, interval=2)

        self.assertEqual(mock_request.call_count, 1)
        mock_sleep.assert_not_called()


class WaitForReadyDeadlineAsyncTests(unittest.IsolatedAsyncioTestCase):
    """Async wait_for_ready must mirror sync deadline semantics."""

    async def asyncSetUp(self) -> None:
        self.client = AsyncChatVectorClient("https://api.chatvector.test", api_key="token")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_polling_sleep_is_capped_by_remaining_time(self) -> None:
        pending = DocumentStatus(document_id="doc-123", status="queued")
        monotonic_values = iter([0.0, 8.0, 8.0, 8.0, 8.0, 10.0, 10.0, 10.0])

        with (
            patch.object(self.client, "get_status", return_value=pending),
            patch("chatvector.async_client.time.monotonic", side_effect=monotonic_values),
            patch("chatvector.async_client.asyncio.sleep", return_value=None) as mock_sleep,
        ):
            with self.assertRaises(ChatVectorTimeoutError):
                await self.client.wait_for_ready("doc-123", timeout=10, interval=5)

        mock_sleep.assert_called_once_with(2.0)


def make_response(
    status_code: int,
    *,
    method: str = "GET",
    url: str = "https://api.chatvector.test/test",
    json_data: object | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        headers=headers,
        request=request,
    )


if __name__ == "__main__":
    unittest.main()
