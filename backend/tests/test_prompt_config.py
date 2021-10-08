"""Tests for system prompt loading and LLM generation config wiring."""

import asyncio

import pytest

import services.answer_service as answer_service
import services.providers as providers_mod


def test_load_system_prompt_returns_stripped_content(tmp_path, monkeypatch):
    prompt_file = tmp_path / "custom_system.txt"
    prompt_file.write_text("  line one\nline two  \n", encoding="utf-8")
    monkeypatch.setattr(answer_service.config, "SYSTEM_PROMPT_PATH", str(prompt_file))
    monkeypatch.setattr(answer_service, "_SYSTEM_PROMPT", None)

    assert answer_service._get_system_prompt() == "line one\nline two"


def test_load_system_prompt_missing_file_raises_clear_file_not_found(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist.txt"
    monkeypatch.setattr(answer_service.config, "SYSTEM_PROMPT_PATH", str(missing))
    monkeypatch.setattr(answer_service, "_SYSTEM_PROMPT", None)

    with pytest.raises(FileNotFoundError) as exc_info:
        answer_service._get_system_prompt()

    msg = str(exc_info.value)
    assert "System prompt file not found" in msg
    assert "SYSTEM_PROMPT_PATH" in msg


def test_persona_loading_resolves_correct_path(monkeypatch):
    """Verify that a valid PROMPT_PERSONA resolves to the correct prompt file."""
    import core.config
    import importlib
    
    # Temporarily remove SYSTEM_PROMPT_PATH so persona logic can trigger
    monkeypatch.delenv("SYSTEM_PROMPT_PATH", raising=False)
    monkeypatch.setenv("PROMPT_PERSONA", "concise")
    
    importlib.reload(core.config)
    
    assert "personas" in core.config.config.SYSTEM_PROMPT_PATH
    assert core.config.config.SYSTEM_PROMPT_PATH.endswith("concise.txt")


def test_custom_prompt_overrides_persona(monkeypatch):
    """Verify that explicit SYSTEM_PROMPT_PATH takes precedence over PROMPT_PERSONA."""
    import core.config
    import importlib
    
    monkeypatch.setenv("SYSTEM_PROMPT_PATH", "/tmp/custom.txt")
    monkeypatch.setenv("PROMPT_PERSONA", "concise")
    
    importlib.reload(core.config)
    
    assert core.config.config.SYSTEM_PROMPT_PATH == "/tmp/custom.txt"


def test_invalid_persona_falls_back_to_default(monkeypatch):
    """Verify that an invalid PROMPT_PERSONA falls back to default."""
    import core.config
    import importlib
    
    monkeypatch.delenv("SYSTEM_PROMPT_PATH", raising=False)
    monkeypatch.setenv("PROMPT_PERSONA", "hacker")
    
    importlib.reload(core.config)
    
    assert "default_system.txt" in core.config.config.SYSTEM_PROMPT_PATH
    assert core.config.config.PROMPT_PERSONA == "default"


@pytest.mark.asyncio
async def test_generate_answer_passes_temperature_and_max_tokens_to_provider(
    monkeypatch,
):
    """Verify that generate_answer forwards config values to the provider."""
    captured: dict = {}

    class _CapturingProvider:
        async def generate(self, prompt, *, system_instruction, temperature, max_output_tokens):
            captured["prompt"] = prompt
            captured["system_instruction"] = system_instruction
            captured["temperature"] = temperature
            captured["max_output_tokens"] = max_output_tokens
            return "mocked answer"

    providers_mod._llm_provider = _CapturingProvider()
    monkeypatch.setattr(answer_service.config, "LLM_TEMPERATURE", 0.7)
    monkeypatch.setattr(answer_service.config, "LLM_MAX_OUTPUT_TOKENS", 512)

    try:
        result = await answer_service.generate_answer("What?", "some context")
    finally:
        providers_mod._llm_provider = None

    answer, latency_ms, model_name = result
    assert answer == "mocked answer"
    assert latency_ms >= 0
    assert model_name == ""
    assert captured["prompt"] == "CONTEXT:\nsome context\n\nQUESTION:\nWhat?"
    assert captured["system_instruction"] == answer_service._SYSTEM_PROMPT
    assert captured["temperature"] == 0.7
    assert captured["max_output_tokens"] == 512


@pytest.mark.asyncio
async def test_generate_answer_retries_transient_provider_errors(monkeypatch):
    """Transient provider failures should be retried before returning a soft error."""
    from unittest.mock import AsyncMock, patch

    from services.providers.base import ProviderRateLimitError

    calls = {"count": 0}

    class _FlakyProvider:
        async def generate(self, prompt, *, system_instruction, temperature, max_output_tokens):
            calls["count"] += 1
            if calls["count"] < 3:
                raise ProviderRateLimitError("Rate exceeded")
            return "recovered answer"

    providers_mod._llm_provider = _FlakyProvider()
    monkeypatch.setattr(answer_service, "_api_key_present", lambda: True)

    try:
        with patch("services.answer_service.retry_async", wraps=answer_service.retry_async) as mock_retry:
            with patch("utils.retry.asyncio.sleep", new_callable=AsyncMock):
                answer, latency_ms, model_name = await answer_service.generate_answer(
                    "What?", "some context"
                )
    finally:
        providers_mod._llm_provider = None

    assert answer == "recovered answer"
    assert latency_ms >= 0
    assert model_name == ""
    assert calls["count"] == 3
    assert mock_retry.call_count == 1


@pytest.mark.asyncio
async def test_generate_answer_returns_soft_error_after_retry_exhaustion(monkeypatch):
    """Exhausted provider retries should return the rate-limit soft error."""
    from unittest.mock import AsyncMock, patch

    from services.providers.base import ProviderRateLimitError

    class _AlwaysRateLimitedProvider:
        async def generate(self, prompt, *, system_instruction, temperature, max_output_tokens):
            raise ProviderRateLimitError("Rate exceeded")

    providers_mod._llm_provider = _AlwaysRateLimitedProvider()
    monkeypatch.setattr(answer_service, "_api_key_present", lambda: True)

    try:
        with patch("utils.retry.asyncio.sleep", new_callable=AsyncMock):
            answer, latency_ms, model_name = await answer_service.generate_answer(
                "What?", "some context"
            )
    finally:
        providers_mod._llm_provider = None

    assert answer == answer_service.LLM_MSG_RATE_LIMIT
    assert latency_ms == 0
    assert model_name == ""


@pytest.mark.asyncio
async def test_generate_answer_wait_for_timeout_returns_soft_error(monkeypatch):
    """Exhausted per-attempt timeouts should return the timeout soft error."""
    from unittest.mock import patch

    monkeypatch.setattr(answer_service, "_api_key_present", lambda: True)

    async def _raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError()

    with patch("services.answer_service.retry_async", side_effect=_raise_timeout):
        answer, latency_ms, model_name = await answer_service.generate_answer(
            "What?", "some context"
        )

    assert answer == answer_service.LLM_MSG_TIMEOUT
    assert latency_ms == 0
    assert model_name == ""
