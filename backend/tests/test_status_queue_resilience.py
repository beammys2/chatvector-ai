"""Tests for /status resilience when queue metrics or Redis fail."""

from unittest.mock import AsyncMock, patch

import pytest

import routes.status as status_module
from routes.status import _build_payload, _format_ascii


@pytest.fixture(autouse=True)
def clear_health_check_cache():
    status_module._HEALTH_CHECK_CACHE.clear()
    status_module._HEALTH_CHECK_CACHE_LOCKS.clear()
    with patch("routes.status.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        yield mock_redis
    status_module._HEALTH_CHECK_CACHE.clear()
    status_module._HEALTH_CHECK_CACHE_LOCKS.clear()


def test_format_ascii_tolerates_unavailable_queue_metrics(monkeypatch):
    monkeypatch.setattr("routes.status.config.QUEUE_BACKEND", "redis")
    payload = {
        "components": {
            "database": "connected",
            "queue": "redis (disconnected)",
            "embeddings": "ok",
            "llm": "ok",
        },
        "metrics": {
            "document_queue": None,
            "workers_active": None,
            "memory_usage": 10,
            "documents_indexed": 0,
        },
        "health_checks": {
            "embedding": {"status": "ok", "latency_ms": 1},
            "llm": {"status": "ok", "latency_ms": 1},
            "redis": {"status": "error", "error": "connection refused"},
        },
        "uptime": "0d 0h 1m",
        "version": "test",
    }

    rendered = _format_ascii(payload)
    assert "unavailable" in rendered
    assert "Workers Active (this process): —/" in rendered


def test_build_payload_when_queue_metrics_unavailable(monkeypatch):
    monkeypatch.setattr("routes.status.config.QUEUE_BACKEND", "redis")

    payload = _build_payload(
        db_ok=True,
        documents_indexed=0,
        memory_pct=10,
        uptime_str="0d 0h 1m",
        version="test",
        queue_pending=None,
        workers_active=None,
        embedding_health={"status": "ok", "latency_ms": 1},
        llm_health={"status": "ok", "latency_ms": 1},
        redis_health={"status": "error", "error": "connection refused"},
    )

    assert payload["status"] == "unhealthy"
    assert payload["components"]["queue"] == "redis (disconnected)"
    assert payload["metrics"]["document_queue"] is None
    assert payload["metrics"]["workers_active"] is None


def test_build_payload_reports_numeric_queue_depth_when_healthy(monkeypatch):
    monkeypatch.setattr("routes.status.config.QUEUE_BACKEND", "redis")

    payload = _build_payload(
        db_ok=True,
        documents_indexed=5,
        memory_pct=10,
        uptime_str="0d 0h 1m",
        version="test",
        queue_pending=3,
        workers_active=2,
        embedding_health={"status": "ok", "latency_ms": 1},
        llm_health={"status": "ok", "latency_ms": 1},
        redis_health={"status": "ok", "latency_ms": 2},
    )

    assert payload["metrics"]["document_queue"] == 3
    assert payload["metrics"]["workers_active"] == 2


@pytest.mark.asyncio
async def test_queue_metrics_helper_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr("routes.status.config.QUEUE_BACKEND", "redis")

    with patch(
        "routes.status.asyncio.to_thread",
        new=AsyncMock(side_effect=ConnectionError("redis down")),
    ):
        pending, workers = await status_module._queue_metrics()

    assert pending is None
    assert workers is None
