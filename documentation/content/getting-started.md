# Getting Started

This guide walks through local setup with Docker, creating an API key, and sending your first chat request.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose
- [Node.js](https://nodejs.org/) and npm (for the frontend demo)
- Either a hosted LLM provider API key (Gemini or OpenAI recommended) or a local [Ollama](https://ollama.com/) installation

## Start the development stack

From the repository root:

```bash
make quickstart
```

The command creates environment files, pauses for provider credentials when needed, installs frontend dependencies, builds the backend Docker image, starts services, and opens browser tabs when ready.

If your provider configuration is already complete, use:

```bash
make
```

Backend-only:

```bash
docker compose up --build
```

When the stack is healthy:

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Frontend demo | http://localhost:3000 |

## Generate an API key

Local development (`APP_ENV=development` or `APP_ENV=test`) bypasses API-key authentication, so you can explore the API without a key.

For production-style auth locally, or before deploying, create a tenant and key with the CLI:

```bash
docker compose exec api python -m backend.cli create-tenant-key \
  --tenant "My Org" \
  --tenant-id my-org
```

The command prints a bearer token once. Store it securely — it cannot be retrieved later.

Use the key on authenticated requests:

```bash
curl -H "Authorization: Bearer cv_live_..." http://localhost:8000/status
```

## First chat flow

=== "curl"

    ```bash
    # 1. Upload a document
    curl -F "file=@handbook.pdf" http://localhost:8000/upload

    # 2. Poll status until completed (replace DOCUMENT_ID)
    curl http://localhost:8000/documents/DOCUMENT_ID/status

    # 3. Ask a question
    curl -X POST http://localhost:8000/chat \
      -H "Content-Type: application/json" \
      -d '{
        "question": "Summarize this document.",
        "doc_id": "DOCUMENT_ID",
        "match_count": 5
      }'
    ```

=== "Python SDK"

    ```python
    from chatvector import ChatVectorClient

    with ChatVectorClient(base_url="http://localhost:8000") as client:
        upload = client.upload_document("handbook.pdf")
        ready = client.wait_for_ready(upload.document_id, timeout=90, interval=3)
        answer = client.chat(
            question="Summarize this document.",
            doc_id=ready.document_id,
            match_count=5,
        )

    print(answer.answer)
    ```

=== "Frontend demo"

    Open http://localhost:3000, upload a PDF or text file, wait for ingestion to finish, then ask a question in the chat panel.

## Sessions and retrieval scopes

For multi-turn conversations, create a session and pass `session_id` on subsequent chat requests. Use `scope` to search within the session (default) or across all tenant documents.

See the [API reference](api-reference.md) for `/sessions` and `/chat` request fields, or the [Python](sdk/python.md) and [TypeScript](sdk/typescript.md) SDK guides for client helpers.

## Next steps

- Browse the full [API reference](api-reference.md)
- Integrate with the [Python SDK](sdk/python.md) or [TypeScript SDK](sdk/typescript.md)
- Read the [deployment guide](deployment.md) before going to production
