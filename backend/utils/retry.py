"""
Async retry with per-attempt timeout, full jitter on backoff, and transient-error
filtering (message patterns + asyncio.TimeoutError). Non-transient errors fail fast.

Example:

    result = await retry_async(
        lambda: service.save(payload),
        max_retries=3,      # up to 3 retries after the first attempt (4 total)
        base_delay=1.0,
        backoff=2.0,
        timeout=10.0,
        func_name="service.save",
    )
"""

import asyncio
import logging
import random
from typing import Type, Tuple, Callable, Any, Optional

logger = logging.getLogger(__name__)

# Shared retry contract (backend services). SDK clients use aligned defaults documented
# in DEVELOPMENT.md — max_retries counts retries *after* the first attempt.
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_BACKOFF = 2.0

# HTTP status codes treated as transient when calling external APIs or in SDK clients.
RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 429, 502, 503, 504})

TRANSIENT_DB_ERROR_PATTERNS = [
    "timeout",
    "connection",
    "deadlock",
    "temporarily",
    "too many clients",
    "network",
    "reset",
    "broken pipe",
    "unavailable",
    "quota",
    "resource_exhausted",
    "rate limit",
]


def get_default_db_timeout_sec() -> float:
    """Outer per-attempt DB deadline; must exceed asyncpg ``command_timeout``."""
    from core.config import config

    return float(config.SQLALCHEMY_STATEMENT_TIMEOUT_SEC) + 5.0


def is_transient_error(exception: Exception) -> bool:
    if isinstance(exception, asyncio.TimeoutError):
        return True

    from services.providers.base import (
        ProviderAuthError,
        ProviderConnectionError,
        ProviderError,
        ProviderRateLimitError,
        ProviderTimeoutError,
    )

    if isinstance(
        exception,
        (ProviderRateLimitError, ProviderTimeoutError, ProviderConnectionError),
    ):
        return True

    if isinstance(exception, (ProviderAuthError, ProviderError)):
        return False

    from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError

    if isinstance(exception, (IntegrityError, DataError, ProgrammingError)):
        return False

    from sqlalchemy.exc import DBAPIError, StatementError

    if isinstance(exception, StatementError):
        orig = exception.orig
        if isinstance(orig, (IntegrityError, DataError, ProgrammingError)):
            return False
        error_str = str(orig if orig is not None else exception).lower()
    elif isinstance(exception, DBAPIError):
        orig = exception.orig
        if isinstance(orig, (IntegrityError, DataError, ProgrammingError)):
            return False
        error_str = str(orig if orig is not None else exception).lower()
    else:
        error_str = str(exception).lower()

    logger.debug("Checking if error is transient: %s", error_str)

    for pattern in TRANSIENT_DB_ERROR_PATTERNS:
        if pattern in error_str:
            logger.debug("Error matched transient pattern: %s", pattern)
            return True

    return False


async def retry_async(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    timeout: float | None = 30.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    func_name: Optional[str] = None,
    retry_on_timeout: bool = True,
) -> Any:
    if func_name is None:
        func_name = getattr(func, '__name__', 'unknown_function')

    last_exception = None
    max_attempts = max_retries + 1

    for attempt in range(max_attempts):
        try:
            if timeout is not None:
                return await asyncio.wait_for(func(), timeout=timeout)
            else:
                return await func()
        except asyncio.TimeoutError as e:
            last_exception = e
            if not retry_on_timeout or attempt == max_attempts - 1:
                logger.error(
                    f"Final attempt timed out for {func_name}",
                    extra={
                        "error_type": "TimeoutError",
                        "timeout_seconds": timeout,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                    },
                )
                raise
            cap = base_delay * (backoff ** attempt)
            delay = random.uniform(0, cap)
            logger.warning(
                f"Attempt {attempt + 1}/{max_attempts} timed out for "
                f"{func_name} after {timeout}s, retrying in {delay:.2f}s",
                extra={
                    "error_type": "TimeoutError",
                    "timeout_seconds": timeout,
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "next_retry_delay": delay,
                },
            )
            await asyncio.sleep(delay)
            continue
        except asyncio.CancelledError:
            raise
        except retryable_exceptions as e:
            last_exception = e

            if not is_transient_error(e):
                logger.error(
                    f"Non-transient error in {func_name}, not retrying",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                    }
                )
                raise

            if attempt == max_attempts - 1:
                logger.error(
                    f"Final attempt failed for {func_name}",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                    }
                )
                raise

            cap = base_delay * (backoff ** attempt)
            delay = random.uniform(0, cap)

            logger.warning(
                f"Transient error in {func_name}, "
                f"retrying in {delay:.2f}s (attempt {attempt + 1}/{max_attempts})",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "next_retry_delay": delay,
                }
            )

            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Unexpected state in retry_async for {func_name}")
