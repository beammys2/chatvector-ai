import { describe, expect, it } from "vitest";
import { hasPartialBatchResult } from "./BatchResultCard";
import type { BatchResultItem } from "../../lib/api";

describe("BatchResultCard helpers", () => {
  it("treats partial error payloads with answer or sources as renderable", () => {
    const partial: BatchResultItem = {
      status: "error",
      question: "Q?",
      doc_ids: ["doc-1"],
      chunks: 1,
      answer: "Partial answer.",
      sources: [{ file_name: "a.pdf", page_number: 1, chunk_index: 0, score: 0.5 }],
      latency_ms: 100,
      model: "m",
      error: { code: "llm_rate_limited", message: "Slow down." },
    };
    expect(hasPartialBatchResult(partial)).toBe(true);
  });

  it("treats error-only payloads without partial content as non-renderable body", () => {
    const errorOnly: BatchResultItem = {
      status: "error",
      question: "Q?",
      doc_ids: ["doc-1"],
      error: { code: "query_processing_failed", message: "Failed." },
    };
    expect(hasPartialBatchResult(errorOnly)).toBe(false);
  });
});
