# FastAPI server-side proxy

This runnable example keeps the ChatVector API key behind a FastAPI backend.
It demonstrates the v0 lifecycle:

```text
uploadDocument -> waitForReady -> createSession -> chat
```

`POST /api/documents` performs the first two operations. `POST /api/chat`
creates an explicit session when the caller does not provide one, then sends
the chat request. `GET /api/documents/{document_id}` exposes status checks
separately.

> [!WARNING]
> This is a server example, not a browser SDK. `CHATVECTOR_API_KEY` is read
> only by this Python process. Do not expose it in browser JavaScript, public
> environment variables, HTML, JSON responses, logs, or the curl commands
> used by your application's clients.

## Run locally

Start the ChatVector backend first (from the repository root):

```bash
make quickstart
```

In a second terminal, install the SDK and example dependencies:

```bash
cd sdk/python
pip install -e .

cd examples/fastapi-proxy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ../..
cp .env.example .env
```

Fill the two server-only values in `.env`:

```dotenv
CHATVECTOR_BASE_URL=http://localhost:8000
CHATVECTOR_API_KEY=your-server-side-key
```

In development mode (`APP_ENV=development`), you can leave `CHATVECTOR_API_KEY`
empty because the backend bypasses authentication locally.

Start the proxy:

```bash
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```

The example listens on http://localhost:3000 by default. Set `PORT` via uvicorn
flags to change it.

## Application authentication boundary

Every `/api/*` request requires an `x-user-id` header as a short, visible
placeholder for the application's own authentication. It is not sufficient
authentication for production: replace the dependency with a verified session or
JWT and enforce document/session ownership in persistent storage.

The application user identity is deliberately separate from ChatVector bearer
authentication. The proxy does not accept a ChatVector key from callers and
does not return its server key in a response.

## Try the flow with curl

Upload a document and wait until ingestion completes:

```sh
curl --fail-with-body --silent --show-error \
  --request POST http://localhost:3000/api/documents \
  --header "x-user-id: user_123" \
  --form "file=@./handbook.pdf;type=application/pdf"
```

The response includes the ready document ID:

```json
{
  "document": {
    "id": "document-id",
    "status": "completed"
  }
}
```

Status can also be checked directly:

```sh
curl --fail-with-body --silent --show-error \
  http://localhost:3000/api/documents/document-id \
  --header "x-user-id: user_123"
```

Ask the first question. With no `sessionId`, the proxy calls
`create_session()` before `chat()` and returns the new ID alongside the answer:

```sh
curl --fail-with-body --silent --show-error \
  --request POST http://localhost:3000/api/chat \
  --header "content-type: application/json" \
  --header "x-user-id: user_123" \
  --data '{"doc_id":"document-id","question":"Summarize this document."}'
```

Continue the same conversation by sending the returned session ID:

```sh
curl --fail-with-body --silent --show-error \
  --request POST http://localhost:3000/api/chat \
  --header "content-type: application/json" \
  --header "x-user-id: user_123" \
  --data '{"doc_id":"document-id","session_id":"session-id","question":"What are the exceptions?","scope":"session"}'
```

## Cancellation and errors

Each route runs its ChatVector work inside a task that is cancelled when the
downstream HTTP client disconnects. Readiness polling also stops when the client
goes away.

`ChatVectorRateLimitError` becomes HTTP 429 and includes a sanitized
`retry_after_ms` value when available. Other `ChatVectorAPIError` instances are
mapped to a safe proxy response; upstream decoded details, causes, and
credentials remain server-side. Upstream authentication failures are treated
as proxy configuration failures and are not presented as the application's
own 401 response.

The 25 MiB upload limit is an example setting. Adjust it together with your
reverse proxy limits and product policy.

## Related examples

- TypeScript Fastify proxy: [`sdk/typescript/examples/fastify-proxy/`](../../../typescript/examples/fastify-proxy/)
- Python SDK scripts: [`sdk/python/examples/`](../)
