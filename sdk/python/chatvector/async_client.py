"""Asynchronous client for interacting with the ChatVector API."""

from __future__ import annotations

import asyncio
import mimetypes
import time
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import httpx

from ._common import (
    JSONDict,
    JSONMapping,
    RETRYABLE_STATUS_CODES,
    build_client_headers,
    cap_duration_to_deadline,
    default_error_message,
    encode_path_component,
    extract_error_details,
    is_retryable_method,
    map_http_error,
    msg_timeout_or_connection,
    msg_unexpected,
    normalize_base_url,
    parse_json_dict,
    remaining_monotonic_seconds,
    request_timeout_for_deadline,
    retry_after_seconds,
    serialize_batch_query,
)
from ._retry import RetryDeadlineExceeded, WantsRetry, retry_async
from ._sse import (
    async_iter_stream_chat_events,
    map_stream_error,
    raise_for_stream_response,
)
from .exceptions import (
    ChatVectorAPIError,
    ChatVectorTimeoutError,
)
from .models import (
    BatchChatQuery,
    BatchChatResponse,
    ChatResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatus,
    RetrievalScope,
    Session,
    SessionHistoryResponse,
    SessionListResponse,
    StreamChatEvent,
)


class AsyncChatVectorClient:
    """Async convenience wrapper around the ChatVector HTTP API."""

    _RETRYABLE_STATUS_CODES = RETRYABLE_STATUS_CODES

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        """
        Create an asynchronous ChatVector API client.

        Args:
            base_url: Root URL for the ChatVector API, such as
                ``https://api.chatvector.example``.
            api_key: Optional bearer token used for authenticated requests.
        """
        normalized_base_url = normalize_base_url(base_url)
        headers = build_client_headers(api_key)

        self.base_url = normalized_base_url
        self.api_key = api_key
        self.max_retries = 2
        self.retry_backoff = 0.5
        self._default_timeout = 30.0
        self._client = httpx.AsyncClient(
            base_url=normalized_base_url,
            headers=headers,
            timeout=self._default_timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "AsyncChatVectorClient":
        """Support use as an async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """Close the underlying HTTP client when exiting a context manager."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def upload_document(self, file_path: str) -> DocumentResponse:
        """
        Upload a document for ingestion.

        The SDK targets ``POST /ingest`` and transparently falls back to the
        repository's current ``POST /upload`` route when needed.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Document file was not found: {file_path}")

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        endpoints = ("ingest", "upload")
        last_error: ChatVectorAPIError | None = None

        for endpoint in endpoints:
            with path.open("rb") as file_handle:
                files = {"file": (path.name, file_handle, content_type)}
                try:
                    payload = await self._request_json("POST", endpoint, files=files)
                    return DocumentResponse.from_dict(payload)
                except ChatVectorAPIError as exc:
                    if endpoint == "ingest" and exc.status_code == 404:
                        last_error = exc
                        continue
                    raise

        if last_error is None:
            raise ChatVectorAPIError("Document upload failed for an unknown reason.")
        raise last_error

    async def get_status(
        self,
        document_id: str,
        *,
        deadline_monotonic: float | None = None,
    ) -> DocumentStatus:
        """Fetch the ingestion status for a document."""
        encoded_id = encode_path_component(document_id)
        payload = await self._request_json(
            "GET",
            f"documents/{encoded_id}/status",
            deadline_monotonic=deadline_monotonic,
        )
        return DocumentStatus.from_dict(payload)

    async def list_documents(self) -> DocumentListResponse:
        """List document summaries for the authenticated tenant."""
        payload = await self._request_json("GET", "documents")
        return DocumentListResponse.from_dict(payload)

    async def delete_document(self, document_id: str) -> None:
        """Delete a document by identifier."""
        encoded_id = encode_path_component(document_id)
        await self._request_no_content("DELETE", f"documents/{encoded_id}")

    async def create_session(self, session_id: str | None = None) -> Session:
        """Create a new chat session."""
        body: JSONDict = {}
        if session_id is not None:
            body["session_id"] = session_id
        payload = await self._request_json("POST", "sessions", json=body)
        return Session.from_dict(payload)

    async def get_session(self, session_id: str) -> Session:
        """Fetch session metadata by identifier."""
        payload = await self._request_json(
            "GET",
            f"sessions/{encode_path_component(session_id)}",
        )
        return Session.from_dict(payload)

    async def get_session_history(self, session_id: str) -> SessionHistoryResponse:
        """Fetch chat message history for a session."""
        encoded_id = encode_path_component(session_id)
        payload = await self._request_json("GET", f"sessions/{encoded_id}/history")
        return SessionHistoryResponse.from_dict(payload)

    async def list_sessions(self) -> SessionListResponse:
        """List all sessions for the authenticated tenant."""
        payload = await self._request_json("GET", "sessions")
        return SessionListResponse.from_dict(payload)

    async def delete_session(self, session_id: str) -> None:
        """Delete a session by identifier."""
        await self._request_no_content(
            "DELETE",
            f"sessions/{encode_path_component(session_id)}",
        )

    async def chat(
        self,
        question: str,
        doc_id: str,
        match_count: int = 5,
        session_id: str | None = None,
        scope: RetrievalScope | None = None,
    ) -> ChatResponse:
        """Ask a question against a single document."""
        payload: JSONDict = {
            "question": question,
            "doc_id": doc_id,
            "match_count": match_count,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if scope is not None:
            payload["scope"] = scope
        response_payload = await self._request_json("POST", "chat", json=payload)
        return ChatResponse.from_dict(response_payload)

    def stream_chat(
        self,
        question: str,
        doc_id: str,
        match_count: int = 5,
        session_id: str | None = None,
        scope: RetrievalScope | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncIterator[StreamChatEvent]:
        """Stream a chat answer as typed Server-Sent Events."""
        payload: JSONDict = {
            "question": question,
            "doc_id": doc_id,
            "match_count": match_count,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if scope is not None:
            payload["scope"] = scope

        request_kwargs: JSONDict = {"json": payload}
        if timeout is not None:
            request_kwargs["timeout"] = timeout

        return self._aiter_stream_chat_events(request_kwargs)

    async def _aiter_stream_chat_events(
        self,
        request_kwargs: JSONDict,
    ) -> AsyncIterator[StreamChatEvent]:
        """Open a streaming chat request and yield parsed SSE events."""
        try:
            async with self._client.stream("POST", "chat/stream", **request_kwargs) as response:
                raise_for_stream_response(response, self._map_http_error)
                try:
                    async for event in async_iter_stream_chat_events(
                        response.aiter_lines(),
                        map_error=map_stream_error,
                    ):
                        yield event
                finally:
                    await response.aclose()
        except httpx.TimeoutException as exc:
            raise ChatVectorTimeoutError(self._msg_timeout_or_connection()) from exc
        except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            raise ChatVectorTimeoutError(self._msg_timeout_or_connection()) from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc.response) from exc
        except httpx.RequestError as exc:
            raise ChatVectorAPIError(
                msg_unexpected(), details={"error": str(exc)}
            ) from exc

    async def batch_chat(
        self,
        queries: Sequence[BatchChatQuery | JSONMapping],
        session_id: str | None = None,
        scope: RetrievalScope | None = None,
    ) -> BatchChatResponse:
        """Run multiple chat queries in a single API call.

        A batch item that names exactly one document is compare-style: session
        history is not injected and successful turns are not persisted, even when
        ``session_id`` is set.
        """
        payload: JSONDict = {
            "queries": [self._serialize_batch_query(query) for query in queries],
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if scope is not None:
            payload["scope"] = scope
        response_payload = await self._request_json("POST", "chat/batch", json=payload)
        return BatchChatResponse.from_dict(response_payload)

    async def wait_for_ready(
        self,
        document_id: str,
        timeout: int = 60,
        interval: int = 2,
    ) -> DocumentStatus:
        """Poll the document status endpoint until ingestion completes or fails."""
        if timeout <= 0:
            raise ValueError("timeout must be greater than 0.")
        if interval <= 0:
            raise ValueError("interval must be greater than 0.")

        deadline = time.monotonic() + timeout
        last_response: DocumentStatus | None = None

        while True:
            if remaining_monotonic_seconds(deadline) == 0.0:
                raise self._wait_timeout_error(document_id, timeout, last_response)
            try:
                last_response = await self.get_status(
                    document_id,
                    deadline_monotonic=deadline,
                )
            except RetryDeadlineExceeded:
                raise self._wait_timeout_error(document_id, timeout, last_response) from None
            status = last_response.status

            if status == "completed":
                return last_response

            if status == "failed":
                message = f"Document '{document_id}' processing failed."
                error_payload = last_response.error
                if isinstance(error_payload, dict):
                    error_message = error_payload.get("message")
                    if isinstance(error_message, str) and error_message:
                        message = f"{message} {error_message}"
                raise ChatVectorAPIError(message, details=last_response.to_dict())

            remaining = remaining_monotonic_seconds(deadline)
            if remaining is None or remaining <= 0:
                raise self._wait_timeout_error(document_id, timeout, last_response)

            await asyncio.sleep(cap_duration_to_deadline(float(interval), deadline))

    def _wait_timeout_error(
        self,
        document_id: str,
        timeout: int,
        last_response: DocumentStatus | None,
    ) -> ChatVectorTimeoutError:
        """Build the standard wait-for-ready timeout exception."""
        details = last_response.to_dict() if last_response is not None else None
        return ChatVectorTimeoutError(
            f"Timed out after {timeout} second(s) while waiting for document "
            f"'{document_id}' to be ready.",
            status_code=408,
            details=details,
        )

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        deadline_monotonic: float | None = None,
        **kwargs: Any,
    ) -> JSONDict:
        """Send an HTTP request and return the decoded JSON object response."""
        response = await self._request_response(
            method,
            url,
            deadline_monotonic=deadline_monotonic,
            **kwargs,
        )
        return self._parse_json_dict(response)

    async def _request_no_content(
        self,
        method: str,
        url: str,
        *,
        deadline_monotonic: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Send an HTTP request that returns no response body on success."""
        await self._request_response(
            method,
            url,
            deadline_monotonic=deadline_monotonic,
            **kwargs,
        )

    async def _request_response(
        self,
        method: str,
        url: str,
        *,
        deadline_monotonic: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send an HTTP request with retry support and return the raw response."""
        max_attempts = self.max_retries + 1
        call_idx = [0]
        retryable_method = is_retryable_method(method)
        request_kwargs = dict(kwargs)
        if "timeout" not in request_kwargs:
            request_kwargs["timeout"] = request_timeout_for_deadline(
                self._default_timeout,
                deadline_monotonic,
            )

        async def _attempt() -> httpx.Response:
            i = call_idx[0]
            call_idx[0] += 1
            if (
                deadline_monotonic is not None
                and remaining_monotonic_seconds(deadline_monotonic) == 0.0
            ):
                raise RetryDeadlineExceeded()
            per_attempt_kwargs = dict(request_kwargs)
            per_attempt_kwargs["timeout"] = request_timeout_for_deadline(
                float(per_attempt_kwargs.get("timeout", self._default_timeout)),
                deadline_monotonic,
            )
            try:
                response = await self._client.request(method, url, **per_attempt_kwargs)
                if response.status_code in self._RETRYABLE_STATUS_CODES:
                    if retryable_method and i + 1 < max_attempts:
                        raise WantsRetry(self._retry_after_seconds(response))
                    response.raise_for_status()
                    return response
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                if retryable_method and i + 1 < max_attempts:
                    raise WantsRetry(0.0) from exc
                raise ChatVectorTimeoutError(self._msg_timeout_or_connection()) from exc
            except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                if retryable_method and i + 1 < max_attempts:
                    raise WantsRetry(0.0) from exc
                raise ChatVectorTimeoutError(self._msg_timeout_or_connection()) from exc
            except httpx.HTTPStatusError as exc:
                if (
                    retryable_method
                    and exc.response.status_code in self._RETRYABLE_STATUS_CODES
                    and i + 1 < max_attempts
                ):
                    raise WantsRetry(self._retry_after_seconds(exc.response)) from exc
                raise self._map_http_error(exc.response) from exc
            except httpx.RequestError as exc:
                raise ChatVectorAPIError(
                    msg_unexpected(), details={"error": str(exc)}
                ) from exc

        return await retry_async(
            _attempt,
            max_retries=self.max_retries,
            base_delay=self.retry_backoff,
            backoff=2.0,
            func_name="_request_response",
            deadline_monotonic=deadline_monotonic,
        )

    def _map_http_error(self, response: httpx.Response) -> ChatVectorAPIError:
        """Convert an HTTP error response into the matching ChatVector exception."""
        return map_http_error(response)

    def _extract_error_details(self, response: httpx.Response) -> tuple[str, Any | None]:
        """Extract a readable error message and payload from an HTTP response."""
        return extract_error_details(response)

    def _parse_json_dict(self, response: httpx.Response) -> JSONDict:
        """Decode a response body as a JSON object."""
        return parse_json_dict(response)

    def _default_error_message(self, status_code: int) -> str:
        """Return a classification-based fallback error message."""
        return default_error_message(status_code)

    def _retry_after_seconds(self, response: httpx.Response) -> float:
        """Parse Retry-After as seconds, or 0.0 if absent or invalid."""
        return retry_after_seconds(response)

    def _serialize_batch_query(self, query: BatchChatQuery | JSONMapping) -> JSONDict:
        """Normalize a batch query into the JSON payload expected by the API."""
        return serialize_batch_query(query)

    def _msg_timeout_or_connection(self) -> str:
        """Return the standard timeout or connection failure message."""
        return msg_timeout_or_connection()
