import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InfoPopover } from "./InfoPopover";

describe("InfoPopover", () => {
  it("toggles helper text when the info button is clicked", async () => {
    render(
      <InfoPopover label="Scope help">
        Session limits retrieval to documents attached to this session.
      </InfoPopover>
    );

    expect(
      screen.queryByText("Session limits retrieval to documents attached to this session.")
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Scope help" }));
    expect(
      screen.getByText("Session limits retrieval to documents attached to this session.")
    ).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Scope help" }));
    expect(
      screen.queryByText("Session limits retrieval to documents attached to this session.")
    ).not.toBeInTheDocument();
  });
});
