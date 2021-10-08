"""Tests for API key DB access using the primary SQLAlchemy engine."""

from db import get_db_service
from services.api_key_service import _get_session_factory, reset_session_factory


def test_api_key_session_factory_reuses_primary_engine():
    reset_session_factory()
    service = get_db_service()
    factory = _get_session_factory()
    assert factory is service.async_session
    reset_session_factory()
