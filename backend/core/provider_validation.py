"""Provider configuration validation for mixed LLM + embedding setups."""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.provider_capabilities import (
    EMBEDDING_CAPABILITIES,
    EMBEDDING_PROVIDER_NAMES,
    LLM_CAPABILITIES,
    LLM_PROVIDER_NAMES,
    ProviderCapabilities,
    SUPPORTED_MIXED_COMBINATIONS,
)


class ProviderConfigError(ValueError):
    """Raised when LLM/embedding provider configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ProviderConfigSnapshot:
    """Minimal settings needed to validate provider configuration."""

    llm_provider: str
    embedding_provider: str
    enable_streaming: bool
    env: dict[str, str | None]


def _is_configured_value(value: str | None, placeholders: frozenset[str]) -> bool:
    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return stripped not in placeholders


def _credential_error(cap: ProviderCapabilities, env: dict[str, str | None]) -> str | None:
    if cap.api_key_env_var is None:
        return None

    raw = env.get(cap.api_key_env_var)
    if _is_configured_value(raw, cap.placeholder_values):
        return None

    if raw is None or not str(raw).strip():
        state = "missing or empty"
    else:
        state = "set to a placeholder value"

    role_label = "LLM" if cap.role == "llm" else "embedding"
    return (
        f"{role_label} provider {cap.name!r} requires {cap.api_key_env_var} "
        f"({state}). Set it in backend/.env — see backend/.env.example."
    )


def validate_provider_configuration(snapshot: ProviderConfigSnapshot) -> None:
    """Validate an LLM + embedding provider configuration.

    Raises ``ProviderConfigError`` with actionable messages when the
    configuration is invalid. Mixed-provider combinations are allowed when
    each side is independently valid.
    """
    errors: list[str] = []
    llm = snapshot.llm_provider.strip().lower()
    embedding = snapshot.embedding_provider.strip().lower()

    if llm not in LLM_PROVIDER_NAMES:
        valid = ", ".join(sorted(LLM_PROVIDER_NAMES))
        errors.append(f"Invalid LLM_PROVIDER={llm!r}. Expected one of: {valid}.")

    if embedding not in EMBEDDING_PROVIDER_NAMES:
        valid = ", ".join(sorted(EMBEDDING_PROVIDER_NAMES))
        errors.append(
            f"Invalid EMBEDDING_PROVIDER={embedding!r}. Expected one of: {valid}."
        )

    if llm in LLM_PROVIDER_NAMES and embedding in EMBEDDING_PROVIDER_NAMES:
        if (llm, embedding) not in SUPPORTED_MIXED_COMBINATIONS:
            errors.append(
                f"Unsupported provider combination LLM={llm!r} + "
                f"embedding={embedding!r}."
            )
        else:
            llm_cap = LLM_CAPABILITIES[llm]
            emb_cap = EMBEDDING_CAPABILITIES[embedding]

            if cred_err := _credential_error(llm_cap, snapshot.env):
                errors.append(cred_err)
            if cred_err := _credential_error(emb_cap, snapshot.env):
                errors.append(cred_err)

            if snapshot.enable_streaming and not llm_cap.supports_streaming:
                errors.append(
                    f"ENABLE_STREAMING=true but LLM provider {llm!r} does not "
                    "support streaming. Choose a streaming-capable LLM provider "
                    "or set ENABLE_STREAMING=false."
                )

    if errors:
        combo_hint = (
            f"Configured combination: LLM={llm} + embedding={embedding}. "
            "Mixed providers are supported when credentials are configured."
        )
        message = "Provider configuration is invalid:\n" + "\n".join(
            f"  - {err}" for err in errors
        )
        message += f"\n{combo_hint}"
        raise ProviderConfigError(message)


def validate_provider_configuration_from_env(
    *,
    llm_provider: str,
    embedding_provider: str,
    enable_streaming: bool,
) -> None:
    """Validate provider configuration using the current process environment."""
    env = {key: os.getenv(key) for key in _tracked_env_vars()}
    snapshot = ProviderConfigSnapshot(
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        enable_streaming=enable_streaming,
        env=env,
    )
    validate_provider_configuration(snapshot)


def _tracked_env_vars() -> set[str]:
    vars_: set[str] = set()
    for cap in (*LLM_CAPABILITIES.values(), *EMBEDDING_CAPABILITIES.values()):
        if cap.api_key_env_var:
            vars_.add(cap.api_key_env_var)
    return vars_
