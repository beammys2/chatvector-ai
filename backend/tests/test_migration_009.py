"""Tests for migration 009: documents.tenant_id NOT NULL enforcement."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "db"
    / "init"
    / "009_documents_tenant_id_not_null.sql"
)
MIGRATION_FILENAME = "009_documents_tenant_id_not_null.sql"


def _executable_sql() -> str:
    return "\n".join(
        line
        for line in MIGRATION_PATH.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    ).strip()


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_is_atomic_and_self_records():
    sql = _executable_sql()
    assert re.match(r"BEGIN\s*;", sql, re.IGNORECASE)
    assert MIGRATION_FILENAME in sql
    assert re.search(
        r"ON\s+CONFLICT\s*\(\s*filename\s*\)\s+DO\s+NOTHING\s*;"
        r"\s*COMMIT\s*;\s*$",
        sql,
        re.IGNORECASE,
    )


def test_migration_aborts_on_null_rows_without_recording_ledger():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "tenant_id IS NULL" in sql
    assert "RAISE EXCEPTION" in sql
    assert "RETURN;" not in sql.replace("RETURNING", "")


def test_migration_replaces_set_null_fk_with_cascade():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "ON DELETE CASCADE" in sql
    assert "ON DELETE SET NULL" in sql


@pytest.fixture
def postgres_connection():
    psycopg = pytest.importorskip("psycopg")
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
    )
    dsn = re.sub(r"^postgresql\+(?:asyncpg|psycopg)://", "postgresql://", database_url)

    try:
        connection = psycopg.connect(dsn, connect_timeout=2)
    except psycopg.OperationalError as exc:
        if os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}:
            pytest.fail(f"PostgreSQL is required for migration tests in CI: {exc}")
        pytest.skip(f"PostgreSQL is unavailable: {exc}")

    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def test_009_end_to_end_null_rows_abort_then_apply_after_backfill(postgres_connection):
    """NULL tenant_id must abort 009 without ledger row; backfill then succeeds."""
    psycopg = pytest.importorskip("psycopg")
    conn = postgres_connection
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    conn.autocommit = False
    doc_id: str | None = None
    tenant_id = f"test-009-{uuid4().hex[:8]}"

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            if cur.fetchone()[0] is None:
                pytest.skip("schema_migrations is not installed")

            cur.execute(
                "DELETE FROM public.schema_migrations WHERE filename = %s",
                (MIGRATION_FILENAME,),
            )
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'documents'
                   AND column_name = 'tenant_id'
                   AND is_nullable = 'YES'
                """
            )
            if cur.fetchone() is None:
                cur.execute(
                    "ALTER TABLE documents ALTER COLUMN tenant_id DROP NOT NULL"
                )

            cur.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (tenant_id, tenant_id),
            )
            doc_id = str(uuid4())
            cur.execute(
                "INSERT INTO documents (id, file_name, tenant_id, status) "
                "VALUES (%s, %s, NULL, 'completed')",
                (doc_id, "orphan-doc.sql"),
            )
        conn.commit()

        with pytest.raises(
            psycopg.errors.RaiseException,
            match="009_documents_tenant_id_not_null.sql cannot proceed",
        ):
            with conn.cursor() as cur:
                cur.execute(migration_sql)
            conn.commit()
        conn.rollback()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM public.schema_migrations WHERE filename = %s",
                (MIGRATION_FILENAME,),
            )
            assert cur.fetchone() is None

            cur.execute(
                """
                SELECT is_nullable FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'documents'
                   AND column_name = 'tenant_id'
                """
            )
            assert cur.fetchone()[0] == "YES"

            cur.execute(
                "UPDATE documents SET tenant_id = %s WHERE id = %s",
                (tenant_id, doc_id),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(migration_sql)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM public.schema_migrations WHERE filename = %s",
                (MIGRATION_FILENAME,),
            )
            assert cur.fetchone() is not None

            cur.execute(
                """
                SELECT is_nullable FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'documents'
                   AND column_name = 'tenant_id'
                """
            )
            assert cur.fetchone()[0] == "NO"

            cur.execute(
                """
                SELECT rc.delete_rule
                  FROM information_schema.referential_constraints rc
                  JOIN information_schema.table_constraints tc
                    ON rc.constraint_name = tc.constraint_name
                 WHERE tc.constraint_name = 'fk_documents_tenant_id'
                """
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "CASCADE"
    finally:
        conn.rollback()
        if doc_id is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                    cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                conn.commit()
                with conn.cursor() as cur:
                    cur.execute(migration_sql)
                conn.commit()
            except Exception:
                conn.rollback()
        conn.autocommit = True
