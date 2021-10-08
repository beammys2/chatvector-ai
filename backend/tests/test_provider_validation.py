"""Tests for provider capability definitions and configuration validation."""

from __future__ import annotations

import pytest

from db.migration_ledger import migration_filenames
from core.provider_capabilities import (
    EMBEDDING_CAPABILITIES,
    EMBEDDING_PROVIDER_NAMES,
    LLM_CAPABILITIES,
    LLM_PROVIDER_NAMES,
    SUPPORTED_MIXED_COMBINATIONS,
)
from core.provider_validation import (
    ProviderConfigError,
    ProviderConfigSnapshot,
    validate_provider_configuration,
    validate_provider_configuration_from_env,
)


def _env(**overrides: str | None) -> dict[str, str | None]:
    base = {
        "GEN_AI_KEY": "real-gemini-key",
        "OPENAI_API_KEY": "real-openai-key",
        "ANTHROPIC_API_KEY": "real-anthropic-key",
        "VOYAGE_API_KEY": "real-voyage-key",
    }
    base.update(overrides)
    return base


def _snapshot(
    llm: str = "gemini",
    embedding: str = "gemini",
    *,
    enable_streaming: bool = False,
    env: dict[str, str | None] | None = None,
) -> ProviderConfigSnapshot:
    return ProviderConfigSnapshot(
        llm_provider=llm,
        embedding_provider=embedding,
        enable_streaming=enable_streaming,
        env=env if env is not None else _env(),
    )


class TestProviderCapabilities:
    def test_llm_providers_support_streaming(self):
        for name, cap in LLM_CAPABILITIES.items():
            assert cap.supports_streaming, f"{name} LLM must support streaming"

    def test_supported_combination_count(self):
        assert len(SUPPORTED_MIXED_COMBINATIONS) == len(LLM_PROVIDER_NAMES) * len(
            EMBEDDING_PROVIDER_NAMES
        )

    def test_voyage_is_embedding_only(self):
        assert "voyage" in EMBEDDING_PROVIDER_NAMES
        assert "voyage" not in LLM_PROVIDER_NAMES

    def test_anthropic_is_llm_only(self):
        assert "anthropic" in LLM_PROVIDER_NAMES
        assert "anthropic" not in EMBEDDING_PROVIDER_NAMES


class TestValidateProviderConfiguration:
    @pytest.mark.parametrize(
        ("llm", "embedding"),
        sorted(SUPPORTED_MIXED_COMBINATIONS),
    )
    def test_all_supported_combinations_pass_with_credentials(self, llm, embedding):
        validate_provider_configuration(_snapshot(llm, embedding))

    def test_anthropic_plus_voyage_mixed_provider(self):
        validate_provider_configuration(
            _snapshot("anthropic", "voyage", env=_env())
        )

    def test_invalid_llm_provider(self):
        with pytest.raises(ProviderConfigError, match="Invalid LLM_PROVIDER='unknown'"):
            validate_provider_configuration(_snapshot("unknown", "gemini"))

    def test_invalid_embedding_provider(self):
        with pytest.raises(ProviderConfigError, match="Invalid EMBEDDING_PROVIDER='unknown'"):
            validate_provider_configuration(_snapshot("gemini", "unknown"))

    def test_missing_anthropic_key_for_mixed_config(self):
        env = _env(ANTHROPIC_API_KEY=None)
        with pytest.raises(ProviderConfigError, match="ANTHROPIC_API_KEY"):
            validate_provider_configuration(_snapshot("anthropic", "voyage", env=env))

    def test_missing_voyage_key_for_mixed_config(self):
        env = _env(VOYAGE_API_KEY="your_voyage_api_key_here")
        with pytest.raises(ProviderConfigError, match="VOYAGE_API_KEY"):
            validate_provider_configuration(_snapshot("anthropic", "voyage", env=env))

    def test_placeholder_gemini_key_rejected(self):
        env = _env(GEN_AI_KEY="your_google_ai_studio_api_key_here")
        with pytest.raises(ProviderConfigError, match="GEN_AI_KEY"):
            validate_provider_configuration(_snapshot("gemini", "gemini", env=env))

    def test_ollama_requires_no_api_keys(self):
        env = {
            "GEN_AI_KEY": None,
            "OPENAI_API_KEY": None,
            "ANTHROPIC_API_KEY": None,
            "VOYAGE_API_KEY": None,
        }
        validate_provider_configuration(_snapshot("ollama", "ollama", env=env))

    def test_error_message_includes_combination_hint(self):
        env = _env(ANTHROPIC_API_KEY=None)
        with pytest.raises(ProviderConfigError, match="Mixed providers are supported"):
            validate_provider_configuration(_snapshot("anthropic", "voyage", env=env))

    def test_streaming_enabled_with_streaming_llm_passes(self):
        for llm in LLM_PROVIDER_NAMES:
            validate_provider_configuration(
                _snapshot(llm, "gemini", enable_streaming=True)
            )


class TestValidateFromEnv:
    def test_reads_process_environment(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("EMBEDDING_PROVIDER", "voyage")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("VOYAGE_API_KEY", "voyage-test")
        validate_provider_configuration_from_env(
            llm_provider="anthropic",
            embedding_provider="voyage",
            enable_streaming=False,
        )


class TestProviderFactoryIndependence:
    """Ensure mixed providers instantiate separate singletons."""

    def test_anthropic_llm_with_voyage_embedding(self, monkeypatch):
        import services.providers as providers_mod

        providers_mod._embedding_provider = None
        providers_mod._llm_provider = None
        monkeypatch.setattr(providers_mod.config, "LLM_PROVIDER", "anthropic")
        monkeypatch.setattr(providers_mod.config, "EMBEDDING_PROVIDER", "voyage")

        llm = providers_mod.get_llm_provider()
        emb = providers_mod.get_embedding_provider()

        assert type(llm).__name__ == "AnthropicLLMProvider"
        assert type(emb).__name__ == "VoyageEmbeddingProvider"
        assert llm is not emb

        providers_mod._embedding_provider = None
        providers_mod._llm_provider = None


class TestStartupValidation:
    @pytest.mark.asyncio
    async def test_lifespan_skips_validation_in_test_env(self, monkeypatch):
        from unittest.mock import AsyncMock, patch

        from fastapi import FastAPI
        from main import lifespan

        monkeypatch.setenv("APP_ENV", "test")
        app = FastAPI()

        with patch("main.config.APP_ENV", "test"), \
             patch("main.validate_provider_configuration_from_env") as mock_validate, \
             patch("main.config.DATABASE_URL", "postgresql+asyncpg://x"), \
             patch(
                 "main._read_migration_ledger_with_retry",
                 new_callable=AsyncMock,
                 return_value=migration_filenames(),
             ), \
             patch("main.db.fail_stale_documents_global", new_callable=AsyncMock, return_value=set()), \
             patch("main.ingestion_queue.start", new_callable=AsyncMock), \
             patch("main.ingestion_queue.stop", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_lifespan_validates_in_development_env(self, monkeypatch):
        from unittest.mock import AsyncMock, patch

        from fastapi import FastAPI
        from main import lifespan

        monkeypatch.setenv("APP_ENV", "development")
        app = FastAPI()

        with patch("main.config.APP_ENV", "development"), \
             patch("main.config.QUEUE_BACKEND", "memory"), \
             patch("main.validate_provider_configuration_from_env") as mock_validate, \
             patch("main.config.DATABASE_URL", "postgresql+asyncpg://x"), \
             patch(
                 "main._read_migration_ledger_with_retry",
                 new_callable=AsyncMock,
                 return_value=migration_filenames(),
             ), \
             patch("main.db.fail_stale_documents_global", new_callable=AsyncMock, return_value=set()), \
             patch(
                 "services.api_key_service.bootstrap_development_tenant",
                 new_callable=AsyncMock,
             ), \
             patch("main.ingestion_queue.start", new_callable=AsyncMock), \
             patch("main.ingestion_queue.stop", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_validate.assert_called_once()
