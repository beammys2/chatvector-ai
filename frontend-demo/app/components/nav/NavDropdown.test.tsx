import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import NavDropdown from "./NavDropdown";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("NavDropdown", () => {
  it("opens the menu on hover and exposes demo links", async () => {
    const onFlyoutOpenChange = vi.fn();

    const { rerender } = render(
      <ul>
        <NavDropdown
          label="Demo"
          links={[
            { label: "Chat", href: "/chat" },
            { label: "Batch", href: "/batch" },
          ]}
          isActive={false}
          flyoutOpen={false}
          onFlyoutOpenChange={onFlyoutOpenChange}
          menuId="demo-menu"
        />
      </ul>
    );

    const trigger = screen.getByRole("button", { name: "Demo" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    fireEvent.mouseEnter(trigger.closest("li")!);
    expect(onFlyoutOpenChange).toHaveBeenCalledWith(true);

    rerender(
      <ul>
        <NavDropdown
          label="Demo"
          links={[
            { label: "Chat", href: "/chat" },
            { label: "Batch", href: "/batch" },
          ]}
          isActive={false}
          flyoutOpen={true}
          onFlyoutOpenChange={onFlyoutOpenChange}
          menuId="demo-menu"
        />
      </ul>
    );

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Chat" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("menuitem", { name: "Batch" })).toHaveAttribute("href", "/batch");
  });

  it("exposes docs links when open", () => {
    render(
      <ul>
        <NavDropdown
          label="Docs"
          links={[{ label: "Development", href: "/docs/development" }]}
          isActive={false}
          flyoutOpen={true}
          onFlyoutOpenChange={vi.fn()}
          menuId="docs-menu"
        />
      </ul>
    );

    expect(screen.getByRole("menuitem", { name: "Development" })).toHaveAttribute(
      "href",
      "/docs/development"
    );
  });
});
