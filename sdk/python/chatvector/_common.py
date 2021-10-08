"""Shared HTTP helpers for sync and async ChatVector clients."""

from __future__ import annotations

import time
from typing import Any, Mapping
from urllib.parse import quote

import httpx

from .exceptions import (
    ChatVectorAPIError,
    ChatVectorAuthError,
    ChatVectorRateLimitError,
    ChatVectorTimeoutError,
)
from .models import BatchChatQuery

JSONDict = dict[str, Any]
JSONMapping = Mapping[str, Any]

RETRYABLE_STATUS_CODES = {408, 429, 502, 503, 504}

# SDK defaults aligned with the TypeScript client (see DEVELOPMENT.md).
DEFAULT_SDK_MAX_RETRIES = 2
DEFAULT_SDK_BASE_DELAY = 0.5
DEFAULT_SDK_BACKOFF = 2.0
DEFAULT_SDK_MAX_DELAY = 8.0


def is_retryable_method(method: str) -> bool:
    """Only safe, idempotent reads are automatically replayed."""
    normalized = method.upper()
    return normalized in {"GET", "HEAD"}


def encode_path_component(value: str) -> str:
    """Encode one URL path segment (TypeScript ``encodeURIComponent`` semantics)."""
    return quote(value, safe="")


def remaining_monotonic_seconds(deadline_monotonic: float | None) -> float | None:
    """Return seconds until ``deadline_monotonic``, or ``None`` when unset."""
    if deadline_monotonic is None:
        return None
    return max(0.0, deadline_monotonic - time.monotonic())


def cap_duration_to_deadline(duration: float, deadline_monotonic: float | None) -> float:
    """Cap a sleep or request timeout to the remaining wall-clock budget."""
    remaining = remaining_monotonic_seconds(deadline_monotonic)
    if remaining is None:
        return duration
    return min(duration, remaining)


def request_timeout_for_deadline(
    default_timeout: float,
    deadline_monotonic: float | None,
) -> float:
    """Choose an httpx timeout that respects an optional absolute deadline."""
    remaining = remaining_monotonic_seconds(deadline_monotonic)
    if remaining is None:
        return default_timeout
    if remaining <= 0:
        return 0.001
    return min(default_timeout, remaining)


def map_http_error(response: httpx.Response) -> ChatVectorAPIError:
    """Convert an HTTP error response into the matching ChatVector exception."""
    message, details = extract_error_details(response)
    error_class: type[ChatVectorAPIError] = ChatVectorAPIError

    if response.status_code in {401, 403}:
        error_class = ChatVectorAuthError
    elif response.status_code == 429:
        error_class = ChatVectorRateLimitError
    elif response.status_code in {408, 504}:
        error_class = ChatVectorTimeoutError

    return error_class(
        message,
        status_code=response.status_code,
        details=details,
        response=response,
    )


def extract_error_details(response: httpx.Response) -> tuple[str, Any | None]:
    """Extract a readable error message and payload from an HTTP response."""
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        if text:
            return text, None
        return default_error_message(response.status_code), None

    if not isinstance(payload, dict):
        return default_error_message(response.status_code), payload

    detail = payload.get("detail", payload)

    if isinstance(detail, dict):
        message = detail.get("message")
        code = detail.get("code")
        if isinstance(message, str) and message:
            if isinstance(code, str) and code:
                return f"{message} ({code})", detail
            return message, detail

    if isinstance(detail, str) and detail:
        return detail, detail

    return default_error_message(response.status_code), detail


def parse_json_dict(response: httpx.Response) -> JSONDict:
    """Decode a response body as a JSON object."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise ChatVectorAPIError(
            "ChatVector returned a non-JSON response.",
            status_code=response.status_code,
            response=response,
        ) from exc

    if not isinstance(payload, dict):
        raise ChatVectorAPIError(
            "ChatVector returned an unexpected response shape.",
            status_code=response.status_code,
            details=payload,
            response=response,
        )

    return payload


def default_error_message(status_code: int) -> str:
    """Return a classification-based fallback error message."""
    if status_code in {401, 403}:
        return msg_invalid_api_key()
    if status_code == 429:
        return msg_rate_limit()
    if status_code in {408, 504}:
        return msg_timeout_or_connection()
    return msg_unexpected()


def retry_after_seconds(response: httpx.Response) -> float:
    """Parse Retry-After as seconds, or 0.0 if absent or invalid."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return 0.0
    try:
        return max(0.0, float(retry_after))
    except ValueError:
        return 0.0


def serialize_batch_query(query: BatchChatQuery | JSONMapping) -> JSONDict:
    """Normalize a batch query into the JSON payload expected by the API."""
    if isinstance(query, BatchChatQuery):
        return query.to_dict()
    if isinstance(query, Mapping):
        return dict(query)
    raise TypeError("Each batch query must be a BatchChatQuery instance or a mapping.")


def build_client_headers(api_key: str | None) -> dict[str, str]:
    """Build default HTTP headers for ChatVector API requests."""
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def normalize_base_url(base_url: str) -> str:
    """Validate and normalize a ChatVector API base URL."""
    if not base_url.strip():
        raise ValueError("base_url must not be empty.")
    return base_url.rstrip("/")


def msg_invalid_api_key() -> str:
    """Return the standard authentication failure message."""
    return "ChatVector request failed: invalid or unauthorized API key."


def msg_rate_limit() -> str:
    """Return the standard rate-limit failure message."""
    return "ChatVector request failed: rate limit or quota exceeded. Please try again later."


def msg_timeout_or_connection() -> str:
    """Return the standard timeout or connection failure message."""
    return "ChatVector request failed: the service timed out or could not be reached."


def msg_unexpected() -> str:
    """Return the standard unexpected failure message."""
    return "ChatVector request failed due to an unexpected error."
