-- API key lifecycle: optional expiration and external user mapping.
--
-- Adds nullable expires_at and external_user_id columns to api_keys.
-- expires_at is indexed for expiry checks during validation.
-- external_user_id is indexed for operator lookups by developer-side identity.

BEGIN;

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS external_user_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at
    ON api_keys(expires_at)
    WHERE expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_api_keys_external_user_id
    ON api_keys(external_user_id)
    WHERE external_user_id IS NOT NULL;

INSERT INTO public.schema_migrations (filename)
VALUES ('010_api_key_lifecycle.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
