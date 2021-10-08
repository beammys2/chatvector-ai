# TypeScript SDK

`@chatvector/sdk` is the official Node-first TypeScript client for upload, readiness polling, chat, batch operations, sessions, and streaming.

Full details: [`sdk/typescript/README.md`](https://github.com/chatvector-ai/chatvector-ai/blob/main/sdk/typescript/README.md).

!!! warning "Server-side only"
    Never expose a ChatVector API key in browser code, `NEXT_PUBLIC_*` variables, or responses sent to clients. This package is for Node backends only.

## Installation

```bash
npm install @chatvector/sdk
```

From the monorepo during development:

```bash
cd sdk/typescript
npm ci
npm run build
```

## Quickstart

```typescript
import { ChatVectorClient } from "@chatvector/sdk";

const client = new ChatVectorClient({
  baseUrl: process.env.CHATVECTOR_BASE_URL!,
  apiKey: process.env.CHATVECTOR_API_KEY!,
  timeoutMs: 30_000,
});

const uploaded = await client.uploadDocument({
  path: "./documents/handbook.pdf",
  contentType: "application/pdf",
});

await client.waitForReady(uploaded.documentId, {
  timeoutMs: 60_000,
  pollIntervalMs: 2_000,
});

const session = await client.createSession();
const answer = await client.chat({
  question: "What is the vacation policy?",
  docId: uploaded.documentId,
  sessionId: session.id,
  matchCount: 5,
  scope: "session",
});

console.log(answer.answer);
```

## Streaming chat

When the backend has streaming enabled (`ENABLE_STREAMING=true`), use `streamChat()` to consume Server-Sent Events:

```typescript
for await (const event of client.streamChat({
  question: "Summarize this document.",
  docId: uploaded.documentId,
  sessionId: session.id,
})) {
  if (event.type === "token") process.stdout.write(event.content ?? "");
  if (event.type === "complete") console.log(event.sources);
}
```

## Reference implementation

The Fastify proxy example demonstrates a server-side integration pattern — upload, wait-for-ready, session creation, and scoped chat with downstream cancellation:

- [`sdk/typescript/examples/fastify-proxy/`](https://github.com/chatvector-ai/chatvector-ai/tree/main/sdk/typescript/examples/fastify-proxy)

Run it after building the SDK:

```bash
cd sdk/typescript
npm ci && npm run build
cd examples/fastify-proxy
npm install
cp .env.example .env
# set CHATVECTOR_BASE_URL and CHATVECTOR_API_KEY
npm start
```

## Error handling

Catch `ChatVectorRateLimitError` for 429 responses (includes optional `retryAfterMs`) and `ChatVectorAPIError` for other API failures. See the [README](https://github.com/chatvector-ai/chatvector-ai/blob/main/sdk/typescript/README.md) for streaming, batch, and session helpers.
