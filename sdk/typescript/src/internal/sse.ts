import {
  ChatVectorAPIError,
  ChatVectorAuthError,
  ChatVectorRateLimitError,
  ChatVectorTimeoutError,
} from "../errors.js";
import type { ChatSource, ChatStreamEvent } from "../models.js";
import { redactSecret, redactText } from "./redact.js";
import { abortReason } from "./time.js";
import { isRecord, stringValue } from "./utils.js";

const DONE_PAYLOAD = "[DONE]";
const MAX_MALFORMED_SSE_DATA_CHARS = 256;

export type StreamParseOptions = {
  signal?: AbortSignal;
  apiKey?: string;
};

type StreamErrorPayload = {
  code: string;
  message: string;
  raw: Record<string, unknown>;
};

export function mapStreamError(
  error: StreamErrorPayload,
  apiKey?: string,
): ChatVectorAPIError {
  const message = redactText(
    error.message || "ChatVector streaming request failed.",
    apiKey,
  );
  const details = redactSecret(error.raw, apiKey) as Record<string, unknown>;

  if (error.code === "llm_missing_api_key" || error.code === "llm_invalid_api_key") {
    return new ChatVectorAuthError(message, { details });
  }
  if (error.code === "llm_rate_limited") {
    return new ChatVectorRateLimitError(message, { details });
  }
  if (error.code === "llm_timeout_or_connection") {
    return new ChatVectorTimeoutError(message, { details });
  }
  return new ChatVectorAPIError(message, {
    ...(error.code ? { code: error.code } : {}),
    details,
  });
}

export async function* iterChatStreamEvents(
  response: Response,
  options: StreamParseOptions = {},
): AsyncGenerator<ChatStreamEvent> {
  const { signal, apiKey } = options;
  if (response.body === null) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName: string | null = null;
  let dataLines: string[] = [];

  const dispatchBufferedEvent = (): ChatStreamEvent | null => {
    if (eventName === null && dataLines.length === 0) {
      return null;
    }
    const event = dispatchSseEvent(eventName, dataLines.join("\n"), apiKey);
    eventName = null;
    dataLines = [];
    return event;
  };

  try {
    while (true) {
      throwIfAborted(signal);

      const { done, value } = await readStreamChunk(reader, signal);
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      let newlineIndex = buffer.indexOf("\n");
      while (newlineIndex !== -1) {
        const line = buffer.slice(0, newlineIndex).replace(/\r$/, "");
        buffer = buffer.slice(newlineIndex + 1);
        newlineIndex = buffer.indexOf("\n");

        if (line === "") {
          const event = dispatchBufferedEvent();
          if (event !== null) {
            yield event;
          }
          continue;
        }

        if (line.startsWith("event:")) {
          eventName = line.slice("event:".length).trim() || null;
          continue;
        }

        if (line.startsWith("data:")) {
          dataLines.push(line.slice("data:".length).trim());
        }
      }
    }

    buffer += decoder.decode();
    if (buffer.length > 0) {
      const trailingLine = buffer.replace(/\r$/, "");
      if (trailingLine.startsWith("event:")) {
        eventName = trailingLine.slice("event:".length).trim() || null;
      } else if (trailingLine.startsWith("data:")) {
        dataLines.push(trailingLine.slice("data:".length).trim());
      }
    }

    const trailingEvent = dispatchBufferedEvent();
    if (trailingEvent !== null) {
      yield trailingEvent;
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // Cancellation errors are not authoritative for callers.
    }
  }
}

async function readStreamChunk(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  signal?: AbortSignal,
): Promise<ReadableStreamReadResult<Uint8Array>> {
  let rejectInterruption: ((reason: unknown) => void) | undefined;
  const interruption = new Promise<never>((_resolve, reject) => {
    rejectInterruption = reject;
  });
  const onAbort = (): void => {
    rejectInterruption?.(abortReason(signal!));
  };

  signal?.addEventListener("abort", onAbort, { once: true });
  if (signal?.aborted) {
    onAbort();
  }

  try {
    return await Promise.race([reader.read(), interruption]);
  } catch (error) {
    try {
      void reader.cancel().catch(() => undefined);
    } catch {
      // The abort reason below remains authoritative for callers.
    }
    if (signal?.aborted) {
      throw abortReason(signal);
    }
    throw error;
  } finally {
    signal?.removeEventListener("abort", onAbort);
  }
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw abortReason(signal);
  }
}

function dispatchSseEvent(
  eventName: string | null,
  data: string,
  apiKey?: string,
): ChatStreamEvent | null {
  if (eventName === "done" || data === DONE_PAYLOAD) {
    return null;
  }

  if (eventName === "error") {
    const payload = parseJsonObject(data, "error");
    throw mapStreamError(parseStreamErrorPayload(payload), apiKey);
  }

  if (eventName === "token") {
    const content = parseJsonValue(data, "token");
    if (typeof content !== "string") {
      throw new ChatVectorAPIError(
        "ChatVector returned an unexpected token event payload.",
        { details: { event: "token", payload: content } },
      );
    }
    return { type: "token", content };
  }

  if (eventName === "complete") {
    const payload = parseJsonObject(data, "complete");
    return {
      type: "complete",
      sessionId: nullableString(payload.session_id),
      sources: mapSources(payload.sources),
      latencyMs: numberValue(payload.latency_ms),
      model: stringValue(payload.model),
      _raw: payload,
    };
  }

  throw new ChatVectorAPIError(
    "ChatVector returned an unexpected streaming event.",
    { details: { event: eventName, data: truncateMalformedData(data) } },
  );
}

function parseStreamErrorPayload(payload: Record<string, unknown>): StreamErrorPayload {
  return {
    code: stringValue(payload.code),
    message: stringValue(payload.message),
    raw: payload,
  };
}

function parseJsonObject(data: string, eventType: string): Record<string, unknown> {
  const payload = parseJsonValue(data, eventType);
  if (!isRecord(payload)) {
    throw new ChatVectorAPIError(
      "ChatVector returned an unexpected streaming event payload.",
      { details: { event: eventType, payload } },
    );
  }
  return payload;
}

function parseJsonValue(data: string, eventType: string): unknown {
  try {
    return JSON.parse(data) as unknown;
  } catch {
    throw new ChatVectorAPIError(
      "ChatVector returned a non-JSON streaming event payload.",
      {
        details: {
          event: eventType,
          data: truncateMalformedData(data),
        },
      },
    );
  }
}

function truncateMalformedData(data: string): string {
  return data.length <= MAX_MALFORMED_SSE_DATA_CHARS
    ? data
    : `${data.slice(0, MAX_MALFORMED_SSE_DATA_CHARS)}…`;
}

function mapSources(value: unknown): ChatSource[] {
  return Array.isArray(value)
    ? value.filter(isRecord).map((source) => {
        const result: ChatSource = {
          fileName: nullableString(source.file_name),
          pageNumber: nullableNumber(source.page_number),
          chunkIndex: nullableNumber(source.chunk_index),
        };
        if (source.score === null || typeof source.score === "number") {
          result.score = source.score;
        }
        if (source.score_type === null || typeof source.score_type === "string") {
          result.scoreType = source.score_type;
        }
        return result;
      })
    : [];
}

function numberValue(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function nullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
