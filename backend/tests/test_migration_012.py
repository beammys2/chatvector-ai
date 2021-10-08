"""Tests for migration 012: reconcile documents.tenant_id NOT NULL."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

import pytest

MIGRATION_009_FILENAME = "009_documents_tenant_id_not_null.sql"
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "db"
    / "init"
    / "012_documents_tenant_id_not_null_reconcile.sql"
)
MIGRATION_FILENAME = "012_documents_tenant_id_not_null_reconcile.sql"


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


def test_012_false_009_ledger_null_rows_fails_without_012_ledger(postgres_connection):
    """False 009 ledger + NULL rows: 012 fails and does not record itself."""
    psycopg = pytest.importorskip("psycopg")
    conn = postgres_connection
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    conn.autocommit = False
    doc_id: str | None = None
    tenant_id = f"test-012-{uuid4().hex[:8]}"

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            if cur.fetchone()[0] is None:
                pytest.skip("schema_migrations is not installed")

            cur.execute(
                "DELETE FROM public.schema_migrations WHERE filename IN (%s, %s)",
                (MIGRATION_009_FILENAME, MIGRATION_FILENAME),
            )
            cur.execute(
                "ALTER TABLE documents ALTER COLUMN tenant_id DROP NOT NULL"
            )
            cur.execute(
                """
                ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_tenant_id
                """
            )
            cur.execute(
                """
                ALTER TABLE documents
                    ADD CONSTRAINT fk_documents_tenant_id
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                    ON DELETE SET NULL
                """
            )
            cur.execute(
                "INSERT INTO public.schema_migrations (filename) VALUES (%s) "
                "ON CONFLICT (filename) DO NOTHING",
                (MIGRATION_009_FILENAME,),
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
                (doc_id, "orphan-012.sql"),
            )
        conn.commit()

        with pytest.raises(
            psycopg.errors.RaiseException,
            match="012_documents_tenant_id_not_null_reconcile.sql cannot proceed",
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


def test_012_false_009_ledger_clean_rows_repairs_schema(postgres_connection):
    """False 009 ledger + clean rows: 012 enforces NOT NULL and records itself."""
    psycopg = pytest.importorskip("psycopg")
    conn = postgres_connection
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    conn.autocommit = False
    doc_id: str | None = None
    tenant_id = f"test-012-clean-{uuid4().hex[:8]}"

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            if cur.fetchone()[0] is None:
                pytest.skip("schema_migrations is not installed")

            cur.execute(
                "DELETE FROM public.schema_migrations WHERE filename IN (%s, %s)",
                (MIGRATION_009_FILENAME, MIGRATION_FILENAME),
            )
            cur.execute(
                "ALTER TABLE documents ALTER COLUMN tenant_id DROP NOT NULL"
            )
            cur.execute(
                "ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_tenant_id"
            )
            cur.execute(
                """
                ALTER TABLE documents
                    ADD CONSTRAINT fk_documents_tenant_id
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                    ON DELETE SET NULL
                """
            )
            cur.execute(
                "INSERT INTO public.schema_migrations (filename) VALUES (%s) "
                "ON CONFLICT (filename) DO NOTHING",
                (MIGRATION_009_FILENAME,),
            )
            cur.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (tenant_id, tenant_id),
            )
            doc_id = str(uuid4())
            cur.execute(
                "INSERT INTO documents (id, file_name, tenant_id, status) "
                "VALUES (%s, %s, %s, 'completed')",
                (doc_id, "clean-012.sql", tenant_id),
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
