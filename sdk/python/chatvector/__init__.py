"""Public package exports for the ChatVector Python SDK."""

from .client import ChatVectorClient
from .async_client import AsyncChatVectorClient
from .exceptions import (
    ChatVectorAPIError,
    ChatVectorAuthError,
    ChatVectorRateLimitError,
    ChatVectorTimeoutError,
)
from .models import (
    BatchChatQuery,
    BatchChatResponse,
    BatchChatResult,
    ChatResponse,
    ChatSource,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatus,
    DocumentSummary,
    RetrievalScope,
    Session,
    SessionHistoryMessage,
    SessionHistoryResponse,
    SessionListResponse,
    StreamChatEvent,
    StreamErrorEvent,
)

__all__ = [
    "AsyncChatVectorClient",
    "ChatVectorAPIError",
    "ChatVectorAuthError",
    "ChatVectorClient",
    "ChatVectorRateLimitError",
    "ChatVectorTimeoutError",
    "BatchChatQuery",
    "BatchChatResponse",
    "BatchChatResult",
    "ChatResponse",
    "ChatSource",
    "DocumentListResponse",
    "DocumentResponse",
    "DocumentStatus",
    "DocumentSummary",
    "RetrievalScope",
    "Session",
    "SessionHistoryMessage",
    "SessionHistoryResponse",
    "SessionListResponse",
    "StreamChatEvent",
    "StreamErrorEvent",
]
