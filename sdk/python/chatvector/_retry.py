"""Internal sync and async retry helpers with exponential backoff."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Awaitable, Callable, Optional, TypeVar

from ._common import (
    DEFAULT_SDK_BACKOFF,
    DEFAULT_SDK_BASE_DELAY,
    DEFAULT_SDK_MAX_DELAY,
    DEFAULT_SDK_MAX_RETRIES,
    cap_duration_to_deadline,
    remaining_monotonic_seconds,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryDeadlineExceeded(Exception):
    """Raised when a retry loop would exceed the caller's absolute deadline."""


class WantsRetry(Exception):
    """Raised by a retried callable to request another attempt after sleeping."""

    __slots__ = ("min_additional_delay",)

    def __init__(self, min_additional_delay: float = 0.0) -> None:
        super().__init__()
        self.min_additional_delay = max(0.0, float(min_additional_delay))


def _retry_delay_seconds(
    attempt: int,
    *,
    base_delay: float,
    backoff: float,
    max_delay: float,
    min_additional_delay: float,
) -> float:
    cap = min(base_delay * (backoff**attempt), max_delay)
    return max(random.uniform(0, cap), min_additional_delay)


def retry_sync(
    func: Callable[[], T],
    max_retries: int = DEFAULT_SDK_MAX_RETRIES,
    base_delay: float = DEFAULT_SDK_BASE_DELAY,
    backoff: float = DEFAULT_SDK_BACKOFF,
    max_delay: float = DEFAULT_SDK_MAX_DELAY,
    func_name: Optional[str] = None,
    deadline_monotonic: float | None = None,
) -> T:
    """
    Retry a synchronous callable with exponential full jitter.

    Retries when ``func`` raises :class:`WantsRetry`. Sleeps
    ``max(random.uniform(0, cap), exc.min_additional_delay)`` where
    ``cap = min(base_delay * (backoff ** attempt), max_delay)`` before the next
    attempt so callers can raise ``WantsRetry(seconds)`` to honor a minimum
    delay (for example from ``Retry-After``) without putting protocol logic here.

    Args:
        func: Callable to invoke (no arguments).
        max_retries: Retries after the first attempt (``max_retries=2`` -> 3 total).
        base_delay: Initial delay factor in seconds.
        backoff: Exponential multiplier applied per retry attempt.
        max_delay: Upper bound on jitter cap in seconds.
        func_name: Optional label for logging.

    Returns:
        The return value of ``func``.

    Raises:
        The last exception if all attempts fail.
    """
    if func_name is None:
        func_name = getattr(func, "__name__", "unknown_function")

    last_exception: BaseException | None = None
    max_attempts = max_retries + 1

    for attempt in range(max_attempts):
        if (
            deadline_monotonic is not None
            and remaining_monotonic_seconds(deadline_monotonic) == 0.0
        ):
            raise RetryDeadlineExceeded()
        try:
            return func()
        except WantsRetry as e:
            last_exception = e
            if attempt == max_attempts - 1:
                logger.error(
                    "Final retry attempt failed for %s",
                    func_name,
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                    },
                )
                raise

            delay = _retry_delay_seconds(
                attempt,
                base_delay=base_delay,
                backoff=backoff,
                max_delay=max_delay,
                min_additional_delay=float(e.min_additional_delay or 0.0),
            )
            delay = cap_duration_to_deadline(delay, deadline_monotonic)
            if deadline_monotonic is not None:
                remaining = remaining_monotonic_seconds(deadline_monotonic)
                if remaining is None or remaining <= 0.0 or delay >= remaining:
                    raise RetryDeadlineExceeded() from e

            logger.warning(
                "Transient error in %s, retrying in %.2fs (attempt %d/%d)",
                func_name,
                delay,
                attempt + 1,
                max_attempts,
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "next_retry_delay": delay,
                },
            )

            time.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Unexpected state in retry_sync for {func_name}")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    max_retries: int = DEFAULT_SDK_MAX_RETRIES,
    base_delay: float = DEFAULT_SDK_BASE_DELAY,
    backoff: float = DEFAULT_SDK_BACKOFF,
    max_delay: float = DEFAULT_SDK_MAX_DELAY,
    func_name: Optional[str] = None,
    deadline_monotonic: float | None = None,
) -> T:
    """
    Retry an async callable with exponential full jitter.

    Retries when ``func`` raises :class:`WantsRetry`. Sleeps
    ``max(random.uniform(0, cap), exc.min_additional_delay)`` where
    ``cap = min(base_delay * (backoff ** attempt), max_delay)`` before the next
    attempt so callers can raise ``WantsRetry(seconds)`` to honor a minimum
    delay (for example from ``Retry-After``) without putting protocol logic here.

    Args:
        func: Async callable to invoke (no arguments).
        max_retries: Retries after the first attempt (``max_retries=2`` -> 3 total).
        base_delay: Initial delay factor in seconds.
        backoff: Exponential multiplier applied per retry attempt.
        max_delay: Upper bound on jitter cap in seconds.
        func_name: Optional label for logging.

    Returns:
        The return value of ``func``.

    Raises:
        The last exception if all attempts fail.
    """
    if func_name is None:
        func_name = getattr(func, "__name__", "unknown_function")

    last_exception: BaseException | None = None
    max_attempts = max_retries + 1

    for attempt in range(max_attempts):
        if (
            deadline_monotonic is not None
            and remaining_monotonic_seconds(deadline_monotonic) == 0.0
        ):
            raise RetryDeadlineExceeded()
        try:
            return await func()
        except WantsRetry as e:
            last_exception = e
            if attempt == max_attempts - 1:
                logger.error(
                    "Final retry attempt failed for %s",
                    func_name,
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                    },
                )
                raise

            delay = _retry_delay_seconds(
                attempt,
                base_delay=base_delay,
                backoff=backoff,
                max_delay=max_delay,
                min_additional_delay=float(e.min_additional_delay or 0.0),
            )
            delay = cap_duration_to_deadline(delay, deadline_monotonic)
            if deadline_monotonic is not None:
                remaining = remaining_monotonic_seconds(deadline_monotonic)
                if remaining is None or remaining <= 0.0 or delay >= remaining:
                    raise RetryDeadlineExceeded() from e

            logger.warning(
                "Transient error in %s, retrying in %.2fs (attempt %d/%d)",
                func_name,
                delay,
                attempt + 1,
                max_attempts,
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "next_retry_delay": delay,
                },
            )

            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Unexpected state in retry_async for {func_name}")
