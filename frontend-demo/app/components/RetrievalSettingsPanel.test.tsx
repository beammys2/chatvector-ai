import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RetrievalSettingsPanel from "./RetrievalSettingsPanel";
import { DEFAULT_RETRIEVAL_SETTINGS } from "../lib/retrievalSettings";

describe("RetrievalSettingsPanel", () => {
  it("calls scope and match count handlers when controls change", async () => {
    const onScopeChange = vi.fn();
    const onMatchCountChange = vi.fn();

    render(
      <RetrievalSettingsPanel
        settings={DEFAULT_RETRIEVAL_SETTINGS}
        onScopeChange={onScopeChange}
        onMatchCountChange={onMatchCountChange}
      />
    );

    await userEvent.click(screen.getByText("Retrieval settings"));

    await userEvent.click(screen.getByRole("radio", { name: "Tenant" }));
    expect(onScopeChange).toHaveBeenCalledWith("tenant");

    const matchCountInput = screen.getByRole("spinbutton", { name: "Match count" });
    await userEvent.clear(matchCountInput);
    await userEvent.type(matchCountInput, "8");
    expect(onMatchCountChange).toHaveBeenCalled();
  });

  it("hides scope controls when showScope is false", async () => {
    render(
      <RetrievalSettingsPanel
        settings={DEFAULT_RETRIEVAL_SETTINGS}
        onMatchCountChange={vi.fn()}
        showScope={false}
      />
    );

    await userEvent.click(screen.getByText("Retrieval settings"));

    expect(screen.queryByRole("radiogroup", { name: "Retrieval scope" })).not.toBeInTheDocument();
    expect(screen.getByRole("slider")).toBeInTheDocument();
  });
});
