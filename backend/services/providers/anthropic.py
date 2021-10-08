"""Anthropic Claude provider implementation."""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

import anthropic

from core.config import config
from services.providers.base import (
    LLMProvider,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)

# See https://docs.anthropic.com/en/docs/about-claude/models
_DEFAULT_LLM_MODEL = "claude-sonnet-4-20250514"


def _classify_anthropic_error(exc: anthropic.APIError) -> ProviderError:
    if isinstance(exc, anthropic.APITimeoutError):
        return ProviderTimeoutError(str(exc))
    if isinstance(exc, anthropic.APIConnectionError):
        return ProviderConnectionError(str(exc))
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderRateLimitError(str(exc))
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return ProviderAuthError(str(exc))
    return ProviderError(str(exc))


class AnthropicLLMProvider(LLMProvider):
    """LLM provider backed by the Anthropic Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model or config.LLM_MODEL or _DEFAULT_LLM_MODEL
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or config.ANTHROPIC_API_KEY,
            base_url=base_url or config.ANTHROPIC_BASE_URL,
            timeout=float(config.LLM_HTTP_TIMEOUT_MS) / 1000.0,
            max_retries=0,
        )

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str,
        temperature: float,
        max_output_tokens: int,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        try:
            create_kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": max_output_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "system": system_instruction,
                "temperature": temperature,
            }
            if extra_params:
                for key in ("top_p", "top_k", "stop_sequences"):
                    if key in extra_params:
                        create_kwargs[key] = extra_params[key]
            response = await self._client.messages.create(**create_kwargs)
            for block in response.content:
                if block.type == "text":
                    return block.text
            return "No response."

        except anthropic.APIError as exc:
            raise _classify_anthropic_error(exc) from exc

    async def generate_stream(
        self,
        prompt: str,
        *,
        system_instruction: str,
        temperature: float,
        max_output_tokens: int,
        extra_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        try:
            stream_kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": max_output_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "system": system_instruction,
                "temperature": temperature,
            }
            if extra_params:
                for key in ("top_p", "top_k", "stop_sequences"):
                    if key in extra_params:
                        stream_kwargs[key] = extra_params[key]
            async with self._client.messages.stream(**stream_kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

        except anthropic.APIError as exc:
            raise _classify_anthropic_error(exc) from exc
