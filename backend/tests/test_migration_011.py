"""Tests for migration 011: document_chunks (document_id, chunk_index) uniqueness."""

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
    / "011_document_chunks_unique_index.sql"
)
MIGRATION_FILENAME = "011_document_chunks_unique_index.sql"
INDEX_NAME = "idx_document_chunks_document_id_chunk_index"


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


def test_migration_aborts_on_duplicates_without_recording_ledger():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "HAVING COUNT(*) > 1" in sql
    assert "RAISE EXCEPTION" in sql
    assert "duplicate (document_id, chunk_index)" in sql
    assert "RETURN;" not in sql.replace("RETURNING", "")


def test_migration_creates_named_unique_index():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert INDEX_NAME in sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS" in sql


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


def test_011_end_to_end_duplicates_abort_then_apply_after_dedup(postgres_connection):
    """Failed apply must not ledger 011; after dedup, re-run creates index + ledger row."""
    psycopg = pytest.importorskip("psycopg")
    conn = postgres_connection
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    conn.autocommit = False
    extra_chunk_id: str | None = None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            if cur.fetchone()[0] is None:
                pytest.skip("schema_migrations is not installed")

            cur.execute(
                "SELECT document_id, chunk_text, embedding, chunk_index, "
                "page_number, character_offset_start, character_offset_end "
                "FROM document_chunks LIMIT 1"
            )
            template = cur.fetchone()
            if template is None:
                pytest.skip("No document_chunks rows available to clone for duplicate test")

            cur.execute(f"DROP INDEX IF EXISTS public.{INDEX_NAME}")
            cur.execute(
                "DELETE FROM public.schema_migrations WHERE filename = %s",
                (MIGRATION_FILENAME,),
            )

            extra_chunk_id = str(uuid4())
            cur.execute(
                "INSERT INTO document_chunks ("
                "id, document_id, chunk_text, embedding, chunk_index, "
                "page_number, character_offset_start, character_offset_end"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    extra_chunk_id,
                    template[0],
                    template[1],
                    template[2],
                    template[3],
                    template[4],
                    template[5],
                    template[6],
                ),
            )
        conn.commit()

        with pytest.raises(
            psycopg.errors.RaiseException,
            match="011_document_chunks_unique_index.sql cannot proceed",
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
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = %s",
                (INDEX_NAME,),
            )
            assert cur.fetchone() is None

            cur.execute("DELETE FROM document_chunks WHERE id = %s", (extra_chunk_id,))
        conn.commit()
        extra_chunk_id = None

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
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = %s",
                (INDEX_NAME,),
            )
            assert cur.fetchone() is not None
    finally:
        conn.rollback()
        if extra_chunk_id is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM document_chunks WHERE id = %s",
                        (extra_chunk_id,),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
        conn.autocommit = True
