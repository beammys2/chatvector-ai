import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useDocumentPolling } from "./useDocumentPolling";

const mockGetDocumentStatus = vi.fn();

vi.mock("../api", () => ({
  getDocumentStatus: (...args: unknown[]) => mockGetDocumentStatus(...args),
  API_BASE: "http://localhost:8000",
  DocumentNotFoundError: class DocumentNotFoundError extends Error {
    name = "DocumentNotFoundError";
  },
}));

describe("useDocumentPolling", () => {
  const originalEventSource = globalThis.EventSource;

  beforeEach(() => {
    mockGetDocumentStatus.mockReset();
    // Force the authenticated polling path; EventSource cannot send auth headers.
    delete (globalThis as { EventSource?: typeof EventSource }).EventSource;
  });

  afterEach(() => {
    globalThis.EventSource = originalEventSource;
    vi.useRealTimers();
  });

  it("maps status-only backend payloads without a stage field", async () => {
    vi.useFakeTimers();

    mockGetDocumentStatus
      .mockResolvedValueOnce({
        status: "embedding",
        chunks: { processed: 2, total: 10 },
      })
      .mockResolvedValueOnce({
        status: "completed",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:01Z",
      });

    const { result } = renderHook(() =>
      useDocumentPolling("doc-1", "/documents/doc-1/status", "processing"),
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.stage).toBe("embedding");
    expect(result.current.status).toBe("processing");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });

    expect(result.current.stage).toBe("completed");
    expect(result.current.status).toBe("ready");
    expect(mockGetDocumentStatus).toHaveBeenCalledWith("/documents/doc-1/status");
  });
});
