"""API key generation, storage, and validation.

Key format:  cv_live_<8-hex-prefix>.<32-char-urlsafe-secret>

Storage:
  - prefix   — non-secret, stored in plaintext for O(1) lookup
  - key_hash — SHA-256 of the full raw key, compared with hmac.compare_digest

Lookup flow:
  1. Parse prefix from the presented key
  2. Fetch the api_keys row by prefix
  3. SHA-256 hash the presented key
  4. Constant-time compare with stored hash
  5. Verify status == 'active' and key is not expired
  6. Return the associated tenant_id
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime
from typing import Literal, Optional, Union

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from core.models import ApiKey, Tenant


class DevelopmentTenantConfigError(ValueError):
    """Raised when DEV_TENANT_ID is invalid for development bootstrap."""


class AuthStoreUnavailableError(Exception):
    """Raised when API key lookup cannot reach the auth datastore."""

logger = logging.getLogger(__name__)

_KEY_PREFIX_BYTES = 4   # 8 hex chars
_KEY_PREFIX_LEN = _KEY_PREFIX_BYTES * 2
_KEY_SECRET_LEN = 32    # URL-safe base64 chars

ValidateApiKeyResult = Union[tuple[str, str], Literal["revoked", "expired"]]

_session_factory: Optional[sessionmaker] = None


def _get_session_factory() -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        from db import get_db_service

        _session_factory = get_db_service().async_session
    return _session_factory


def reset_session_factory() -> None:
    """Replace the cached session factory (for tests that swap DATABASE_URL)."""
    global _session_factory
    _session_factory = None


def generate_raw_key() -> tuple[str, str, str]:
    """Return (raw_key, prefix, key_hash).

    raw_key  — shown to the user exactly once; never stored
    prefix   — stored in plaintext for fast lookup
    key_hash — SHA-256 hex digest of raw_key; stored in the DB
    """
    prefix = secrets.token_hex(_KEY_PREFIX_BYTES)
    secret = secrets.token_urlsafe(_KEY_SECRET_LEN)
    raw_key = f"cv_live_{prefix}.{secret}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, prefix, key_hash


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _parse_prefix(raw_key: str) -> Optional[str]:
    """Extract the public prefix from a raw API key, or None if malformed."""
    if not raw_key.startswith("cv_live_"):
        return None
    rest = raw_key[len("cv_live_"):]
    dot = rest.find(".")
    if dot <= 0:
        return None
    return rest[:dot]


def _is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    return expires_at <= datetime.utcnow()


async def ensure_tenant_exists(tenant_id: str, name: str) -> bool:
    """Ensure a tenant row exists with the given id.

    Returns True if a new row was inserted, False if it already existed.
    Safe under repeated startup and concurrent inserts (ON CONFLICT DO NOTHING).
    Does not create API keys.
    """
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            stmt = (
                insert(Tenant)
                .values(id=tenant_id, name=name)
                .on_conflict_do_nothing(index_elements=["id"])
            )
            result = await session.execute(stmt)
            created = result.rowcount == 1

    if created:
        logger.info("Created tenant id=%s name=%r", tenant_id, name)
    else:
        logger.info("Tenant already exists: id=%s", tenant_id)
    return created


async def bootstrap_development_tenant(app_env: str) -> None:
    """Ensure DEV_TENANT_ID exists when authentication bypass is active."""
    if app_env.lower() not in ("development", "test"):
        return

    raw = os.getenv("DEV_TENANT_ID", "dev")
    tenant_id = raw.strip()
    if not tenant_id:
        raise DevelopmentTenantConfigError(
            "DEV_TENANT_ID must be non-empty when authentication bypass is active "
            f"(APP_ENV={app_env})."
        )

    await ensure_tenant_exists(tenant_id, f"Development ({tenant_id})")


async def create_tenant(name: str, tenant_id: Optional[str] = None) -> Tenant:
    """Insert a new tenant row and return it."""
    if not tenant_id:
        tenant_id = name.lower().replace(" ", "-")

    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            tenant = Tenant(id=tenant_id, name=name)
            session.add(tenant)
    logger.info("Created tenant id=%s name=%r", tenant_id, name)
    return tenant


async def create_api_key(
    tenant_id: str,
    *,
    external_user_id: str | None = None,
    expires_at: datetime | None = None,
) -> tuple[str, ApiKey]:
    """Create an API key for a tenant.

    Returns (raw_key, ApiKey orm row).  The raw_key is shown once and never
    persisted — only the hash is stored.
    """
    raw_key, prefix, key_hash = generate_raw_key()

    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            api_key = ApiKey(
                tenant_id=tenant_id,
                prefix=prefix,
                key_hash=key_hash,
                status="active",
                external_user_id=external_user_id,
                expires_at=expires_at,
            )
            session.add(api_key)

    logger.info("Created API key prefix=%s for tenant=%s", prefix, tenant_id)
    return raw_key, api_key


async def validate_api_key(raw_key: str) -> ValidateApiKeyResult | None:
    """Validate a raw API key.

    Returns:
      - (tenant_id, api_key_id) on success
      - "revoked" when the hash matches but status != active
      - "expired" when the hash matches, status is active, but expires_at is past
      - None on any other credential failure (malformed, unknown prefix, hash mismatch)

    Raises:
      AuthStoreUnavailableError when the database lookup fails.
    """
    prefix = _parse_prefix(raw_key)
    if prefix is None:
        return None

    presented_hash = _hash_key(raw_key)

    factory = _get_session_factory()
    try:
        async with factory() as session:
            result = await session.execute(
                select(ApiKey).where(ApiKey.prefix == prefix)
            )
            api_key = result.scalar_one_or_none()
    except Exception as exc:
        logger.exception("DB error during API key lookup for prefix=%s", prefix)
        raise AuthStoreUnavailableError("API key lookup failed") from exc

    if api_key is None:
        return None

    try:
        hash_matches = hmac.compare_digest(api_key.key_hash, presented_hash)
    except TypeError:
        logger.warning(
            "Malformed key_hash for prefix=%s during API key validation",
            prefix,
        )
        return None

    if not hash_matches:
        return None

    if api_key.status != "active":
        return "revoked"

    if _is_expired(api_key.expires_at):
        return "expired"

    return api_key.tenant_id, str(api_key.id)


async def list_tenant_keys(tenant_id: str) -> list[ApiKey]:
    """List all API keys for a tenant (metadata only — no raw secrets exist to return)."""

    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.tenant_id == tenant_id)
        )
        return list(result.scalars().all())


async def revoke_api_key(
    tenant_id: str,
    key_id: Optional[str] = None,
    prefix: Optional[str] = None,
) -> bool:
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            query = select(ApiKey).where(ApiKey.tenant_id == tenant_id)
            if key_id:
                query = query.where(ApiKey.id == key_id)
            elif prefix:
                query = query.where(ApiKey.prefix == prefix)
            else:
                return False
            result = await session.execute(query)
            api_key = result.scalar_one_or_none()
            if api_key is None:
                return False

            if api_key.status != "revoked":
                api_key.status = "revoked"

    logger.info("Revoked API key id=%s for tenant=%s", key_id or prefix, tenant_id)
    return True


async def rotate_api_key(tenant_id: str, key_id: str) -> tuple[str, ApiKey] | None:
    """Revoke an existing key and issue a new one for the same tenant.

    Returns (raw_key, new ApiKey) or None when the key is not found.
    """
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            result = await session.execute(
                select(ApiKey).where(
                    ApiKey.tenant_id == tenant_id,
                    ApiKey.id == key_id,
                )
            )
            old_key = result.scalar_one_or_none()
            if old_key is None:
                return None

            if old_key.status != "revoked":
                old_key.status = "revoked"

            raw_key, prefix, key_hash = generate_raw_key()
            new_key = ApiKey(
                tenant_id=tenant_id,
                prefix=prefix,
                key_hash=key_hash,
                status="active",
                external_user_id=old_key.external_user_id,
                expires_at=old_key.expires_at,
            )
            session.add(new_key)

    logger.info(
        "Rotated API key id=%s for tenant=%s -> new id=%s",
        key_id,
        tenant_id,
        new_key.id,
    )
    return raw_key, new_key


async def set_api_key_expiry(
    tenant_id: str,
    key_id: str,
    expires_at: datetime | None,
) -> bool:
    """Set or clear expires_at for a tenant API key."""
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            result = await session.execute(
                select(ApiKey).where(
                    ApiKey.tenant_id == tenant_id,
                    ApiKey.id == key_id,
                )
            )
            api_key = result.scalar_one_or_none()
            if api_key is None:
                return False
            api_key.expires_at = expires_at

    logger.info(
        "Set expiry for API key id=%s tenant=%s expires_at=%s",
        key_id,
        tenant_id,
        expires_at,
    )
    return True


async def set_api_key_external_user_id(
    tenant_id: str,
    key_id: str,
    external_user_id: str | None,
) -> bool:
    """Assign or clear external_user_id for a tenant API key."""
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            result = await session.execute(
                select(ApiKey).where(
                    ApiKey.tenant_id == tenant_id,
                    ApiKey.id == key_id,
                )
            )
            api_key = result.scalar_one_or_none()
            if api_key is None:
                return False
            api_key.external_user_id = external_user_id

    logger.info(
        "Set external_user_id for API key id=%s tenant=%s external_user_id=%r",
        key_id,
        tenant_id,
        external_user_id,
    )
    return True
