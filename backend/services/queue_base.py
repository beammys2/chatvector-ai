"""
Ingestion Queue — Abstract Base & Shared Types
================================================

Defines the interface that every queue backend must implement, plus the
data classes and rate limiter shared across backends.

Mirrors the db/base.py pattern: shared types live here so both the asyncio
and Redis backends can import them without circular dependencies.
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class QueueFull(Exception):
    """Raised when the queue is at capacity."""
    pass


@dataclass
class QueueJob:
    doc_id: str
    file_name: str
    content_type: str
    file_bytes: bytes
    tenant_id: Optional[str] = None
    attempt: int = 0
    enqueued_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class DLQEntry:
    """
    Lightweight dead-letter record kept after a job exhausts all retries.

    File bytes are intentionally omitted to avoid unbounded memory growth
    when large uploads fail repeatedly.
    """
    doc_id: str
    file_name: str
    content_type: str
    attempt: int
    error: str
    tenant_id: Optional[str] = None
    failed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TokenBucketRateLimiter:
    """
    Leaky-token-bucket rate limiter safe across threads and event loops.

    Allows at most ``rate`` acquisitions per second with a burst capacity of
    ``capacity``.  The thread lock protects token accounting; ``asyncio.sleep``
    runs outside the lock so worker threads are not blocked while waiting.
    """

    def __init__(self, rate: float, capacity: float) -> None:
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    async def acquire(self) -> None:
        """Block until a token is available, then consume one."""
        while True:
            wait_time = 0.0
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._capacity, self._tokens + elapsed * self._rate
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                wait_time = (1.0 - self._tokens) / self._rate

            await asyncio.sleep(wait_time)


_process_embedding_limiter: TokenBucketRateLimiter | None = None
_process_embedding_limiter_lock = threading.Lock()


def get_process_embedding_rate_limiter() -> TokenBucketRateLimiter:
    """Return one shared embedding rate limiter for this API process."""
    global _process_embedding_limiter

    if _process_embedding_limiter is not None:
        return _process_embedding_limiter

    with _process_embedding_limiter_lock:
        if _process_embedding_limiter is None:
            from core.config import config

            _process_embedding_limiter = TokenBucketRateLimiter(
                rate=config.QUEUE_EMBEDDING_RPS,
                capacity=config.QUEUE_EMBEDDING_RPS,
            )
        return _process_embedding_limiter


def reset_process_embedding_rate_limiter() -> None:
    """Clear the process limiter — for tests only."""
    global _process_embedding_limiter
    with _process_embedding_limiter_lock:
        _process_embedding_limiter = None


class BaseIngestionQueue(ABC):
    """Interface that every queue backend must implement."""

    @abstractmethod
    async def start(self) -> None:
        """Start background workers. Safe to call multiple times (no-op if running)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop background workers and release resources."""
        ...

    @abstractmethod
    async def enqueue(self, job: QueueJob) -> int:
        """Enqueue a job and return its 1-indexed queue position (never 0)."""
        ...

    @abstractmethod
    def queue_position(self, doc_id: str) -> Optional[int]:
        """Return the 1-indexed position for *doc_id*, or None if not waiting."""
        ...

    @abstractmethod
    def queue_size(self) -> int:
        ...

    @abstractmethod
    def dlq_jobs(self) -> list[DLQEntry]:
        ...

    @abstractmethod
    def active_worker_count(self) -> int:
        """Return workers actively listening in this API process."""
        ...

    def clear_stale_jobs(self, failed_doc_ids: set[str]) -> int:
        """Remove stale jobs for already-failed documents.

        No-op for backends that don't persist jobs across restarts.
        """
        return 0


def is_retryable_ingestion_failure(exc: Exception) -> bool:
    """Return True when a failed ingestion job should consume retry budget."""
    from utils.retry import is_transient_error

    return is_transient_error(exc)
