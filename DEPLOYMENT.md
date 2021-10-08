# Production Deployment Guide

Operator-focused checklist for deploying ChatVector in production. This guide
consolidates the steps spread across `README.md`, `DEVELOPMENT.md`, and
`docker-compose.prod.yml` — use [ARCHITECTURE.md](ARCHITECTURE.md) for system
design detail and [DEVELOPMENT.md](DEVELOPMENT.md) for local development.

---

## Prerequisites

- Docker and Docker Compose (for the bundled production stack), **or** your own
  runtime for the FastAPI backend
- PostgreSQL **with the pgvector extension** enabled
- Redis (required for the production ingestion queue default)
- An LLM/embedding provider API key (for example `GEN_AI_KEY` for Gemini)

Managed Postgres with pgvector is supported (Neon, RDS, Cloud SQL, Supabase
Postgres via direct `DATABASE_URL`, and similar). See
[ARCHITECTURE.md](ARCHITECTURE.md) for the supported database abstraction model.

---

## 1. Configure environment variables

Copy the example file and edit values for production:

```bash
cp backend/.env.example backend/.env.prod
```

Set at minimum:

| Variable | Purpose |
|----------|---------|
| `APP_ENV=production` | Enables API-key auth, disables dev bypass, disables `/docs` |
| `DATABASE_URL` | Async PostgreSQL URL (`postgresql+asyncpg://…`) with pgvector |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Used by the bundled Postgres service in Compose |
| `REDIS_URL` | Redis connection string (for example `redis://redis:6379/0`) |
| `GEN_AI_KEY` | Provider key when using Gemini (see `.env.example` for OpenAI, Anthropic, Ollama, Voyage) |
| `LLM_PROVIDER`, `LLM_MODEL` | Chat model selection |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | Embedding model selection |
| `QUEUE_BACKEND=redis` | Production default (Compose sets this automatically) |
| `CORS_ORIGINS` | Comma-separated allowed browser origins (no `*` with credentials) |

Additional production-oriented defaults in `docker-compose.prod.yml`:

- `QUEUE_WORKER_COUNT` (default `3`)
- `LOG_FORMAT=JSON`
- Single-process Uvicorn (`--workers 1`)

**Supported topology:** Phase 3 runs one API process per container. Redis/RQ worker
threads provide ingestion concurrency within that process. Multiple API processes
or containers are not supported. Concurrency env vars (`QUEUE_WORKER_COUNT`,
`QUEUE_EMBEDDING_RPS`, `RETRIEVAL_MAX_CONCURRENCY`, DB pool sizes) are
process-scoped.

**Never deploy with `APP_ENV=development` or `APP_ENV=test` in a shared or public
environment.** Those modes bypass API-key authentication entirely.

Swagger UI (`/docs`, `/redoc`, `/openapi.json`) is **disabled** when
`APP_ENV=production`.

---

## 2. PostgreSQL and pgvector

ChatVector stores vectors in PostgreSQL using the **pgvector** extension.

- **Fresh Docker volume:** SQL files in `backend/db/init/` run automatically on
  first database startup (including pgvector setup in `001_init.sql`).
- **Existing database:** Do not replay `001_init.sql` on populated data. Inspect
  the migration ledger and apply only missing files — see
  [Database migrations](DEVELOPMENT.md#database-migrations) in `DEVELOPMENT.md`.
- **Managed Postgres:** Enable pgvector on the instance, then point `DATABASE_URL`
  at the database. Apply any missing numbered migrations manually with `psql -f`.

Verify the ledger after upgrades:

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT filename, applied_at FROM public.schema_migrations ORDER BY filename;"
```

If `public.schema_migrations` does not exist on an older volume, follow the
backfill procedure in [DEVELOPMENT.md](DEVELOPMENT.md#database-migrations).

---

## 3. Redis as the production queue

When `APP_ENV=production`, Redis is the default queue backend. The production
Compose file sets:

```env
QUEUE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

Ensure Redis is reachable from the API process before accepting uploads.
`QUEUE_BACKEND=memory` is rejected when `APP_ENV=production`; production
requires Redis/RQ ingestion.

---

## 4. Bootstrap tenant and API keys

Production does **not** auto-create tenants. Bootstrap once per environment
using the **same database environment as the running API container**:

```bash
docker compose -f docker-compose.prod.yml --env-file backend/.env.prod \
  exec api python -m cli create-tenant-key --tenant "My Org" --tenant-id my-org
```

The raw key (`cv_live_…`) is printed **once** and is never stored. Save it
immediately. Clients must send:

```http
Authorization: Bearer cv_live_<prefix>.<secret>
```

Manage keys after bootstrap:

```bash
docker compose -f docker-compose.prod.yml --env-file backend/.env.prod \
  exec api python -m cli list-tenant-keys --tenant-id my-org
docker compose -f docker-compose.prod.yml --env-file backend/.env.prod \
  exec api python -m cli rotate-tenant-key --tenant-id my-org --key-id <key-id>
docker compose -f docker-compose.prod.yml --env-file backend/.env.prod \
  exec api python -m cli set-tenant-key-expiry --tenant-id my-org --key-id <key-id> --expires-at "2027-01-01T00:00:00Z"
docker compose -f docker-compose.prod.yml --env-file backend/.env.prod \
  exec api python -m cli set-tenant-key-external-user-id --tenant-id my-org --key-id <key-id> --external-user-id user_123
docker compose -f docker-compose.prod.yml --env-file backend/.env.prod \
  exec api python -m cli revoke-tenant-key --tenant-id my-org --key-id <key-id>
```

Revoking a key is idempotent.

---

## 5. Start the production Docker Compose stack

`docker-compose.prod.yml` is **standalone** — it does not extend
`docker-compose.yml`. It disables dev bind mounts, runs single-process Uvicorn,
uses JSON logging, and applies resource limits.

```bash
# Start production stack (uses backend/.env.prod)
make prod-up

# Equivalent explicit Compose
docker compose -f docker-compose.prod.yml --env-file backend/.env.prod up -d
```

`make prod-up`, `make prod-down`, and `make prod-build` all pass
`--env-file backend/.env.prod`. Copy `backend/.env.example` to
`backend/.env.prod` and configure it before starting.

Health check endpoint (liveness): `GET http://localhost:8000/health`

Authenticated diagnostics: `GET /status` (not a container readiness probe).

Production Postgres is **not** published on host port 5432. Use
`docker compose -f docker-compose.prod.yml --env-file backend/.env.prod exec db psql ...`
for direct DB access.

Validate the full authenticated upload → ingest → chat path locally:

```bash
./scripts/prod-e2e-smoke.sh
```

---

## 6. Post-deploy verification

1. `GET /health` returns success.
2. Authenticated `POST /upload` (or `/ingest`) accepts a document.
3. `GET /documents/{id}/status` reaches `completed`.
4. Authenticated `POST /chat` returns an answer with sources.
5. Confirm `/docs` returns 404 in production (expected).

---

## Common pitfalls

| Pitfall | What goes wrong | What to do |
|---------|-----------------|------------|
| **`APP_ENV=development` in prod** | All requests bypass auth | Set `APP_ENV=production` |
| **Missing migrations / ledger drift** | Schema errors at runtime | Inspect `schema_migrations`; apply missing SQL files |
| **Re-running `001_init.sql` on existing data** | Data loss | Apply only missing numbered migrations |
| **No API key bootstrap** | No tenant can authenticate | Run `create-tenant-key` once per environment |
| **Redis unreachable** | Upload/queue failures; `/status` may show queue metrics unavailable | Verify `REDIS_URL` and Redis health |
| **`QUEUE_BACKEND=memory` in prod** | Startup validation fails | Set `QUEUE_BACKEND=redis` when `APP_ENV=production` |
| **Multiple API workers/containers** | Unsupported in Phase 3; stale-doc reconciliation and tenant registry break | Run `--workers 1` and one API container |
| **pgvector not enabled** | Embedding storage fails | Enable extension on Postgres host |
| **Expecting `/docs` in prod** | Swagger appears disabled | Use OpenAPI from a dev instance or export schema separately |
| **Embedding provider switch without re-index** | Dimension mismatch errors | Fresh DB or re-embed after changing embedding models |

---

## Related documentation

- [DEVELOPMENT.md](DEVELOPMENT.md) — local development, migration details, auth deep dive
- [ARCHITECTURE.md](ARCHITECTURE.md) — components, database abstraction, auth model
- [backend/.env.example](backend/.env.example) — full environment variable reference
- [docker-compose.prod.yml](docker-compose.prod.yml) — production Compose services

---

## Out of scope for this guide

- Provider-specific runbooks (Neon/RDS click-by-click) — enable pgvector and supply
  `DATABASE_URL`; see provider docs.
- Kubernetes/Helm charts — not included in this repository.
- Changing deployment code — file issues or PRs for infrastructure changes.
