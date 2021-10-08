# API Reference

The reference below is generated from the FastAPI OpenAPI schema exported from `backend/main.py` at documentation build time.

!!! note "Production environments"
    Live Swagger UI (`/docs`), ReDoc (`/redoc`), and `/openapi.json` are **disabled** when `APP_ENV=production`. Use this static reference or export the schema from a non-production environment.

## Authentication

| Environment | Auth behavior |
|-------------|---------------|
| `APP_ENV=development` or `test` | Auth bypass — no API key required |
| `APP_ENV=production` | Bearer token required on protected routes |

Protected routes expect:

```http
Authorization: Bearer cv_live_<prefix>.<secret>
```

Create keys with `python -m backend.cli create-tenant-key`. See [Getting Started](getting-started.md#generate-an-api-key).

## Major routes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload` | Upload a document for background ingestion |
| `GET` | `/documents` | List tenant document summaries |
| `GET` | `/documents/{document_id}/status` | Poll ingestion status |
| `GET` | `/documents/{document_id}/status/stream` | SSE ingestion progress |
| `DELETE` | `/documents/{document_id}` | Delete a document |
| `POST` | `/chat` | RAG chat (non-streaming) |
| `POST` | `/chat/stream` | RAG chat (SSE streaming) |
| `POST` | `/chat/batch` | Batch compare or synthesize |
| `POST` | `/sessions` | Create a chat session |
| `GET` | `/sessions` | List sessions |
| `GET` | `/sessions/{session_id}` | Get session metadata |
| `GET` | `/sessions/{session_id}/history` | Session message history |
| `DELETE` | `/sessions/{session_id}` | Delete a session |
| `GET` | `/status` | Service health and configuration summary |
| `GET` | `/queue/stats` | Ingestion queue statistics |

## Interactive schema

<swagger-ui src="assets/openapi.json"/>
