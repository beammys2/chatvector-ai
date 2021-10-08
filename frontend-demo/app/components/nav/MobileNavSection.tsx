import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { NavLink } from "../../lib/navLinks";

type MobileNavSectionProps = {
  label: string;
  links: ReadonlyArray<NavLink>;
  isActive: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  menuId: string;
  onNavigate: () => void;
};

export default function MobileNavSection({
  label,
  links,
  isActive,
  open,
  onOpenChange,
  menuId,
  onNavigate,
}: MobileNavSectionProps) {
  return (
    <li className="w-full text-center">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => onOpenChange(!open)}
        className={`relative inline-flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0 text-base no-underline transition-colors duration-200 ${
          isActive
            ? "nav-link-active text-foreground"
            : "text-foreground hover:text-accent-text"
        }`}
      >
        {label}
        <ChevronDown
          aria-hidden
          className={`size-[1em] shrink-0 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open ? (
        <ul
          id={menuId}
          className="m-0 mt-3 flex list-none flex-col items-stretch gap-2 p-0 pl-4"
        >
          {links.map(({ label: linkLabel, href }) => (
            <li key={href} className="w-full text-center">
              <Link
                href={href}
                onClick={onNavigate}
                className="block px-4 py-2 text-base text-foreground no-underline transition-colors hover:text-accent-text"
              >
                {linkLabel}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}
