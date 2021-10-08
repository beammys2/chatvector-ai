"""Tests for Redis queue worker shutdown behavior."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from services.queue_redis import RedisIngestionQueue, ThreadSafeWorker


@pytest.mark.asyncio
async def test_stop_sets_stop_requested_on_workers(monkeypatch):
    monkeypatch.setattr("services.queue_redis.config.QUEUE_WORKER_COUNT", 1)
    queue = RedisIngestionQueue()
    worker = ThreadSafeWorker(["chatvector-ingestion-pytest"], connection=MagicMock())
    queue._worker_threads = [threading.Thread()]
    queue._rq_workers = [worker]

    with patch.object(queue, "_join_worker_threads") as join_mock:
        await queue.stop()

    assert worker._stop_requested is True
    join_mock.assert_called_once()


@pytest.mark.asyncio
async def test_stop_does_not_block_event_loop(monkeypatch):
    monkeypatch.setattr("services.queue_redis.config.QUEUE_WORKER_COUNT", 1)
    queue = RedisIngestionQueue()
    queue._worker_threads = [threading.Thread()]

    join_started = threading.Event()
    join_finished = threading.Event()

    def slow_join(_timeout: float) -> None:
        join_started.set()
        time.sleep(0.05)
        join_finished.set()

    progress = asyncio.Event()

    async def waiter() -> None:
        progress.set()

    with patch.object(queue, "_join_worker_threads", side_effect=slow_join):
        stop_task = asyncio.create_task(queue.stop())
        await asyncio.wait_for(waiter(), timeout=0.5)
        assert progress.is_set()
        await asyncio.wait_for(stop_task, timeout=1.0)

    assert join_started.is_set()
    assert join_finished.is_set()


def test_thread_safe_worker_dequeue_timeout_is_one_second():
    worker = ThreadSafeWorker(["q"], connection=MagicMock())
    assert worker.dequeue_timeout == 1


def test_thread_safe_worker_tracks_listening_state():
    worker = ThreadSafeWorker(["q"], connection=MagicMock())
    assert worker.listening is False
    worker.listening = True
    worker.teardown()
    assert worker.listening is False
