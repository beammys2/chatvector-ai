"""Tests for Redis client timeout configuration and non-blocking enqueue."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from core.config import config, redis_connection_kwargs
from services.queue_base import QueueJob
from services.queue_redis import RedisIngestionQueue


def test_redis_connection_kwargs_use_finite_timeouts():
    kwargs = redis_connection_kwargs()
    assert kwargs["socket_timeout"] == config.REDIS_SOCKET_TIMEOUT_SEC
    assert kwargs["socket_connect_timeout"] == config.REDIS_SOCKET_TIMEOUT_SEC
    assert kwargs["socket_timeout"] > 0


def test_lazy_async_redis_client_passes_timeouts():
    from core.clients import _LazyRedisClient

    client = _LazyRedisClient()
    with patch("core.clients.Redis.from_url") as mock_from_url:
        mock_from_url.return_value = MagicMock()
        client.ping()
        mock_from_url.assert_called_once()
        _, kwargs = mock_from_url.call_args
        assert kwargs["socket_timeout"] == config.REDIS_SOCKET_TIMEOUT_SEC
        assert kwargs["socket_connect_timeout"] == config.REDIS_SOCKET_TIMEOUT_SEC


def test_redis_ingestion_queue_sync_clients_use_timeouts():
    with patch("services.queue_redis.redis_lib.Redis.from_url") as mock_from_url:
        mock_from_url.return_value = MagicMock()
        RedisIngestionQueue()
        mock_from_url.assert_called_once_with(
            config.REDIS_URL,
            **redis_connection_kwargs(),
        )


@pytest.mark.asyncio
async def test_redis_enqueue_does_not_block_event_loop():
    service = RedisIngestionQueue.__new__(RedisIngestionQueue)
    service._rq_queue = MagicMock()

    def slow_sync_enqueue(_self, job: QueueJob) -> int:
        time.sleep(0.25)
        return 1

    order: list[str] = []

    async def concurrent_task():
        await asyncio.sleep(0.05)
        order.append("concurrent")
        return "ok"

    with patch.object(RedisIngestionQueue, "_sync_enqueue", slow_sync_enqueue):
        enqueue_task = asyncio.create_task(
            RedisIngestionQueue.enqueue(
                service,
                QueueJob(
                    doc_id="doc-block-test",
                    file_name="t.pdf",
                    content_type="application/pdf",
                    file_bytes=b"bytes",
                ),
            )
        )
        concurrent = asyncio.create_task(concurrent_task())
        await asyncio.wait_for(asyncio.gather(enqueue_task, concurrent), timeout=2.0)

    assert order == ["concurrent"]
