"""Safe display helpers for configured connection URLs (no credentials)."""

from __future__ import annotations

from urllib.parse import urlparse


def safe_url_display(url: str) -> str:
    """Return scheme, host, port, and path/db index — never userinfo or passwords."""
    parsed = urlparse(url)
    scheme = parsed.scheme or "unknown"
    host = parsed.hostname or "unknown"
    path = (parsed.path or "/").lstrip("/") or "0"
    if parsed.port is not None:
        return f"{scheme}://{host}:{parsed.port}/{path}"
    return f"{scheme}://{host}/{path}"
