import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SegmentedControl } from "./SegmentedControl";

describe("SegmentedControl", () => {
  it("switches batch mode between compare and synthesize", async () => {
    const onChange = vi.fn();

    const { rerender } = render(
      <SegmentedControl
        name="batch-mode"
        ariaLabel="Batch query mode"
        value="compare"
        onChange={onChange}
        options={[
          { value: "compare", label: "Compare" },
          { value: "synthesize", label: "Synthesize" },
        ]}
      />
    );

    expect(screen.getByRole("radio", { name: "Compare" })).toBeChecked();

    await userEvent.click(screen.getByRole("radio", { name: "Synthesize" }));
    expect(onChange).toHaveBeenCalledWith("synthesize");

    rerender(
      <SegmentedControl
        name="batch-mode"
        ariaLabel="Batch query mode"
        value="synthesize"
        onChange={onChange}
        options={[
          { value: "compare", label: "Compare" },
          { value: "synthesize", label: "Synthesize" },
        ]}
      />
    );

    expect(screen.getByRole("radio", { name: "Synthesize" })).toBeChecked();
  });
});
