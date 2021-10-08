# Deployment

This page summarizes production deployment. The full operator checklist lives in the repository:

**[DEPLOYMENT.md](https://github.com/chatvector-ai/chatvector-ai/blob/main/DEPLOYMENT.md)**

For system design context, see [ARCHITECTURE.md](https://github.com/chatvector-ai/chatvector-ai/blob/main/ARCHITECTURE.md).

## Overview

ChatVector ships as a FastAPI backend with PostgreSQL (pgvector) and Redis for the production ingestion queue. The bundled `docker-compose.prod.yml` stack is the fastest path to a production-like environment.

## Prerequisites

- Docker and Docker Compose, or your own runtime for the FastAPI service
- PostgreSQL with the **pgvector** extension
- Redis (required for the default production queue backend)
- An LLM/embedding provider API key (for example `GEN_AI_KEY`)

## Critical environment variables

| Variable | Purpose |
|----------|---------|
| `APP_ENV=production` | Enables API-key auth; disables dev bypass and `/docs` |
| `DATABASE_URL` | Async PostgreSQL URL with pgvector |
| `REDIS_URL` | Redis connection for the ingestion queue |
| `GEN_AI_KEY` | Provider key (see `.env.example` for OpenAI, Anthropic, Ollama, Voyage) |
| `LLM_PROVIDER`, `LLM_MODEL` | Chat model selection |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | Embedding model selection |
| `QUEUE_BACKEND=redis` | Production queue default |
| `CORS_ORIGINS` | Allowed browser origins (no `*` with credentials) |

!!! danger "Never use development mode in production"
    `APP_ENV=development` and `APP_ENV=test` bypass API-key authentication entirely.

## Bootstrap tenant and API keys

After the database schema is applied, create the first tenant key:

```bash
python -m backend.cli create-tenant-key --tenant "My Org" --tenant-id my-org
```

Store the printed secret securely. Keys are not retrievable after creation. Use `rotate-tenant-key`, `set-tenant-key-expiry`, and `set-tenant-key-external-user-id` for lifecycle management (see `DEVELOPMENT.md`).

## Production Compose

```bash
cp backend/.env.example backend/.env.prod
# edit values for production
docker compose -f docker-compose.prod.yml up --build -d
```

See [DEPLOYMENT.md](https://github.com/chatvector-ai/chatvector-ai/blob/main/DEPLOYMENT.md) for database setup, health checks, scaling notes, and troubleshooting.

## Hosting this documentation site

This issue covers local builds and CI validation only. Publishing the static site to GitHub Pages or another CDN is a follow-up task.

Build locally with:

```bash
make docs-build
```

Output is written to `documentation/site/`.
