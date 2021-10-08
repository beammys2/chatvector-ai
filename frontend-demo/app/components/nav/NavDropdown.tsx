import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { NavLink } from "../../lib/navLinks";

type NavDropdownProps = {
  label: string;
  links: ReadonlyArray<NavLink>;
  isActive: boolean;
  flyoutOpen: boolean;
  onFlyoutOpenChange: (open: boolean) => void;
  menuId: string;
  align?: "left" | "right";
};

export default function NavDropdown({
  label,
  links,
  isActive,
  flyoutOpen,
  onFlyoutOpenChange,
  menuId,
  align = "left",
}: NavDropdownProps) {
  return (
    <li
      className="group relative"
      onMouseEnter={() => onFlyoutOpenChange(true)}
      onMouseLeave={() => onFlyoutOpenChange(false)}
      onFocusCapture={() => onFlyoutOpenChange(true)}
      onBlurCapture={(e) => {
        const next = e.relatedTarget;
        if (next instanceof Node && e.currentTarget.contains(next)) return;
        onFlyoutOpenChange(false);
      }}
    >
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={flyoutOpen}
        aria-controls={menuId}
        className={`relative flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0 text-[1.15rem] text-base no-underline transition-colors duration-200 ${
          isActive
            ? "nav-link-active text-foreground"
            : "text-foreground hover:text-accent-text"
        }`}
      >
        {label}
        <ChevronDown
          aria-hidden
          className="size-[1em] shrink-0 transition-transform duration-200 group-hover:rotate-180 group-focus-within:rotate-180"
        />
      </button>
      <div
        className={`pointer-events-none invisible absolute ${align === "right" ? "right-0" : "left-0"} top-full z-50 pt-2 opacity-0 transition-[opacity,visibility] duration-200 group-hover:pointer-events-auto group-hover:visible group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:visible group-focus-within:opacity-100`}
      >
        <div
          id={menuId}
          className="min-w-[180px] rounded-xl border border-border bg-surface py-2"
          role="menu"
        >
          {links.map(({ label: linkLabel, href }) => (
            <Link
              key={href}
              href={href}
              role="menuitem"
              className="block px-4 py-2 text-base text-muted no-underline transition-colors hover:text-foreground"
            >
              {linkLabel}
            </Link>
          ))}
        </div>
      </div>
    </li>
  );
}
