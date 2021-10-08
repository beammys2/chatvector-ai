"""Assert shipped production Compose topology constraints."""

from pathlib import Path

import pytest
import yaml


def _compose_file_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "docker-compose.prod.yml",
        here.parents[1].parent / "docker-compose.prod.yml",
        Path("/docker-compose.prod.yml"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    pytest.skip("docker-compose.prod.yml not available in this test environment")


def test_production_compose_uses_single_uvicorn_worker():
    compose_path = _compose_file_path()
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    api_service = data["services"]["api"]
    command = api_service["command"]
    assert isinstance(command, list)
    assert "uvicorn" in command

    workers_idx = command.index("--workers")
    worker_count = command[workers_idx + 1]
    assert worker_count == "1", (
        f"Phase 3 requires --workers 1; found --workers {worker_count!r} in "
        f"{compose_path.name}"
    )


def test_production_compose_db_healthcheck_uses_configured_user():
    compose_path = _compose_file_path()
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    healthcheck = data["services"]["db"]["healthcheck"]["test"]
    command = " ".join(healthcheck) if isinstance(healthcheck, list) else healthcheck
    assert "$$POSTGRES_USER" in command
    assert "$$POSTGRES_DB" in command
    assert "-U postgres" not in command


def test_production_compose_db_does_not_publish_host_port():
    compose_path = _compose_file_path()
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    db_service = data["services"]["db"]
    ports = db_service.get("ports")
    assert ports is None or ports == [], (
        f"Production db service must not publish host ports; found {ports!r}"
    )
