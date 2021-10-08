import { describe, expect, it } from "vitest";
import { apiErrorMessage } from "./apiErrorMessage";
import { BackendApiError } from "./apiErrors";
import { ChatError } from "./api";

describe("apiErrorMessage", () => {
  it("returns BackendApiError messages", () => {
    expect(
      apiErrorMessage(
        new BackendApiError(
          "Too many requests. Please slow down.",
          { code: "rate_limited", message: "Too many requests. Please slow down." },
          429,
        ),
        "fallback",
      ),
    ).toBe("Too many requests. Please slow down.");
  });

  it("returns ChatError messages", () => {
    expect(
      apiErrorMessage(new ChatError("no_document", "Document not found."), "fallback"),
    ).toBe("Document not found.");
  });

  it("falls back for unknown errors", () => {
    expect(apiErrorMessage(new Error(""), "Could not load documents.")).toBe(
      "Could not load documents.",
    );
  });
});
