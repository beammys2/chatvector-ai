"""Tests for safe URL display and redacted Redis logging."""

import logging
from unittest.mock import MagicMock, patch

from utils.url_display import safe_url_display


def test_safe_url_display_omits_credentials():
    url = "redis://:supersecret@localhost:6379/0"
    display = safe_url_display(url)
    assert "supersecret" not in display
    assert display == "redis://localhost:6379/0"


def test_redis_client_init_log_redacts_password(caplog, monkeypatch):
    from core import clients as clients_module

    monkeypatch.setattr(
        clients_module.config,
        "REDIS_URL",
        "redis://:supersecret@localhost:6379/0",
    )
    clients_module._LazyRedisClient._client = None

    with patch("core.clients.Redis.from_url", return_value=MagicMock()):
        client = clients_module._LazyRedisClient()
        with caplog.at_level(logging.INFO, logger="core.clients"):
            client._ensure_client()

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "supersecret" not in messages
    assert "redis://localhost:6379/0" in messages
