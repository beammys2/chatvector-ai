"""Shared tenant-scope validation for database operations."""

from __future__ import annotations


def require_tenant_id(tenant_id: str | None, *, method: str) -> str:
    """Reject missing or empty tenant IDs before tenant-scoped DB access."""
    if tenant_id is None or tenant_id == "":
        raise ValueError(f"{method} requires a non-empty tenant_id")
    return tenant_id
