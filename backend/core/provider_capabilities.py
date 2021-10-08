"""Formal capability definitions for LLM and embedding providers.

Single source of truth for supported provider names, credential requirements,
and feature flags used by configuration validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProviderRole = Literal["llm", "embedding"]


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Static metadata for a supported provider."""

    name: str
    role: ProviderRole
    api_key_env_var: str | None
    supports_streaming: bool = False
    placeholder_values: frozenset[str] = frozenset()


_GEMINI_PLACEHOLDER = frozenset({"your_google_ai_studio_api_key_here"})
_OPENAI_PLACEHOLDER = frozenset({"your_openai_api_key_here"})
_ANTHROPIC_PLACEHOLDER = frozenset({"your_anthropic_api_key_here"})
_VOYAGE_PLACEHOLDER = frozenset({"your_voyage_api_key_here"})

LLM_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "gemini": ProviderCapabilities(
        name="gemini",
        role="llm",
        api_key_env_var="GEN_AI_KEY",
        supports_streaming=True,
        placeholder_values=_GEMINI_PLACEHOLDER,
    ),
    "openai": ProviderCapabilities(
        name="openai",
        role="llm",
        api_key_env_var="OPENAI_API_KEY",
        supports_streaming=True,
        placeholder_values=_OPENAI_PLACEHOLDER,
    ),
    "ollama": ProviderCapabilities(
        name="ollama",
        role="llm",
        api_key_env_var=None,
        supports_streaming=True,
    ),
    "anthropic": ProviderCapabilities(
        name="anthropic",
        role="llm",
        api_key_env_var="ANTHROPIC_API_KEY",
        supports_streaming=True,
        placeholder_values=_ANTHROPIC_PLACEHOLDER,
    ),
}

EMBEDDING_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "gemini": ProviderCapabilities(
        name="gemini",
        role="embedding",
        api_key_env_var="GEN_AI_KEY",
        placeholder_values=_GEMINI_PLACEHOLDER,
    ),
    "openai": ProviderCapabilities(
        name="openai",
        role="embedding",
        api_key_env_var="OPENAI_API_KEY",
        placeholder_values=_OPENAI_PLACEHOLDER,
    ),
    "ollama": ProviderCapabilities(
        name="ollama",
        role="embedding",
        api_key_env_var=None,
    ),
    "voyage": ProviderCapabilities(
        name="voyage",
        role="embedding",
        api_key_env_var="VOYAGE_API_KEY",
        placeholder_values=_VOYAGE_PLACEHOLDER,
    ),
}

LLM_PROVIDER_NAMES = frozenset(LLM_CAPABILITIES)
EMBEDDING_PROVIDER_NAMES = frozenset(EMBEDDING_CAPABILITIES)

# Every supported LLM can pair with every supported embedding provider.
SUPPORTED_MIXED_COMBINATIONS: frozenset[tuple[str, str]] = frozenset(
    (llm, embedding)
    for llm in LLM_PROVIDER_NAMES
    for embedding in EMBEDDING_PROVIDER_NAMES
)
