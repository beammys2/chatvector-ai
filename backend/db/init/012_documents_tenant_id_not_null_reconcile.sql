-- Reconcile documents.tenant_id NOT NULL for installations that recorded
-- 009_documents_tenant_id_not_null.sql without applying the constraint.
--
-- Fresh installs: 009 (fixed) already enforces NOT NULL; this migration is
-- idempotent and records completion for the reconciliation step.
--
-- ────────────────────────────────────────────────────────────────────────────
-- EXISTING INSTALLATIONS WITH NULL tenant_id
-- ────────────────────────────────────────────────────────────────────────────
-- Backfill or delete orphaned rows before applying:
--
--   UPDATE documents SET tenant_id = '<tenant-id>' WHERE tenant_id IS NULL;
--   -- or --
--   DELETE FROM documents WHERE tenant_id IS NULL;
--
-- Then re-run:
--
--   docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--       -v ON_ERROR_STOP=1 \
--       -f /docker-entrypoint-initdb.d/012_documents_tenant_id_not_null_reconcile.sql
--
-- ────────────────────────────────────────────────────────────────────────────
-- ROLLBACK
-- ────────────────────────────────────────────────────────────────────────────
--   ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_tenant_id;
--   ALTER TABLE documents ALTER COLUMN tenant_id DROP NOT NULL;
--   ALTER TABLE documents
--       ADD CONSTRAINT fk_documents_tenant_id
--       FOREIGN KEY (tenant_id) REFERENCES tenants(id)
--       ON DELETE SET NULL;
--   DELETE FROM public.schema_migrations
--    WHERE filename = '012_documents_tenant_id_not_null_reconcile.sql';

BEGIN;

DO $$
DECLARE
    null_count BIGINT;
    is_nullable TEXT;
BEGIN
    SELECT COUNT(*) INTO null_count FROM documents WHERE tenant_id IS NULL;

    IF null_count > 0 THEN
        RAISE EXCEPTION
            'Migration 012_documents_tenant_id_not_null_reconcile.sql cannot proceed: % document(s) still have NULL tenant_id. Backfill or delete orphaned rows, then re-run 012.',
            null_count
            USING HINT = (
                'Example: UPDATE documents SET tenant_id = ''<tenant-id>'' '
                'WHERE tenant_id IS NULL; or DELETE FROM documents WHERE tenant_id IS NULL.'
            );
    END IF;

    SELECT c.is_nullable INTO is_nullable
      FROM information_schema.columns c
     WHERE c.table_schema = 'public'
       AND c.table_name = 'documents'
       AND c.column_name = 'tenant_id';

    IF is_nullable = 'YES' THEN
        ALTER TABLE documents ALTER COLUMN tenant_id SET NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM information_schema.table_constraints
         WHERE constraint_name = 'fk_documents_tenant_id'
           AND table_name = 'documents'
    ) THEN
        ALTER TABLE documents DROP CONSTRAINT fk_documents_tenant_id;
    END IF;

    ALTER TABLE documents
        ADD CONSTRAINT fk_documents_tenant_id
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        ON DELETE CASCADE;
END;
$$;

INSERT INTO public.schema_migrations (filename)
VALUES ('012_documents_tenant_id_not_null_reconcile.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
