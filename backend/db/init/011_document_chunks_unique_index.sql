-- Enforce unique (document_id, chunk_index) on document_chunks.
--
-- ────────────────────────────────────────────────────────────────────────────
-- EXISTING INSTALLATIONS WITH DUPLICATES
-- ────────────────────────────────────────────────────────────────────────────
-- If duplicate (document_id, chunk_index) rows exist, this migration aborts
-- and rolls back. No schema_migrations ledger row is recorded in that case.
--
-- Inspect duplicates with:
--
--   SELECT document_id, chunk_index, COUNT(*) AS cnt
--     FROM document_chunks
--    GROUP BY document_id, chunk_index
--   HAVING COUNT(*) > 1
--    ORDER BY cnt DESC;
--
-- Back up the database, then keep one row per pair (for example the earliest
-- created_at) and delete the rest before applying:
--
--   docker compose exec db psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
--       -f /docker-entrypoint-initdb.d/011_document_chunks_unique_index.sql
--
-- ────────────────────────────────────────────────────────────────────────────
-- ROLLBACK
-- ────────────────────────────────────────────────────────────────────────────
--   DROP INDEX IF EXISTS idx_document_chunks_document_id_chunk_index;
--   DELETE FROM public.schema_migrations
--    WHERE filename = '011_document_chunks_unique_index.sql';

BEGIN;

DO $$
DECLARE
    dup_groups BIGINT;
BEGIN
    SELECT COUNT(*) INTO dup_groups
    FROM (
        SELECT document_id, chunk_index
          FROM document_chunks
         GROUP BY document_id, chunk_index
        HAVING COUNT(*) > 1
    ) AS duplicates;

    IF dup_groups > 0 THEN
        RAISE EXCEPTION
            'Migration 011_document_chunks_unique_index.sql cannot proceed: % duplicate (document_id, chunk_index) group(s) exist. Back up, deduplicate, then re-run this migration.',
            dup_groups
            USING HINT = (
                'Inspect duplicates with SELECT document_id, chunk_index, COUNT(*) '
                'FROM document_chunks GROUP BY 1, 2 HAVING COUNT(*) > 1. '
                'Keep one row per pair, delete the rest, then re-run 011.'
            );
    END IF;

    CREATE UNIQUE INDEX IF NOT EXISTS idx_document_chunks_document_id_chunk_index
        ON document_chunks (document_id, chunk_index);
END;
$$;

INSERT INTO public.schema_migrations (filename)
VALUES ('011_document_chunks_unique_index.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
