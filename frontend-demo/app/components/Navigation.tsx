"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Github } from "lucide-react";
import { useState } from "react";
import MobileNavSection from "./nav/MobileNavSection";
import NavBrand from "./nav/NavBrand";
import NavDropdown from "./nav/NavDropdown";
import ThemeToggle from "./ThemeToggle";
import {
  ABOUT_LINK,
  CONTRIBUTORS_LINK,
  DEMO_LINKS,
  DOC_LINKS,
  GITHUB_REPO,
  isNavGroupActive,
} from "../lib/navLinks";

function NavLinks({
  links,
  onNavigate,
  pathname,
  centerOnMobile = false,
}: {
  links: ReadonlyArray<{ label: string; href: string }>;
  onNavigate?: () => void;
  pathname: string | null;
  centerOnMobile?: boolean;
}) {
  return (
    <>
      {links.map(({ label, href }) => {
        const isActive = pathname === href;
        return (
          <li
            key={label}
            className={centerOnMobile ? "w-full text-center" : undefined}
          >
            <Link
              href={href}
              onClick={onNavigate}
              className={`relative inline-block text-base text-bold no-underline text-[1.15rem] transition-colors duration-200 ${
                isActive
                  ? "nav-link-active text-foreground"
                  : "text-foreground hover:text-accent-text"
              }`}
            >
              {label}
            </Link>
          </li>
        );
      })}
    </>
  );
}

function GitHubNavLink() {
  return (
    <a
      href={GITHUB_REPO}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="View ChatVector on GitHub"
      className="inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-transparent p-2 text-base leading-none text-foreground no-underline transition-all duration-200 hover:border-accent hover:bg-accent/10 hover:text-accent-text md:px-[18px] md:py-2"
    >
      <Github
        className="size-[1.1rem] shrink-0 md:hidden"
        strokeWidth={1.75}
        aria-hidden
      />
      <span className="hidden md:inline">GitHub</span>
    </a>
  );
}

export default function Navigation() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [docsOpen, setDocsOpen] = useState(false);
  const [demoFlyoutOpen, setDemoFlyoutOpen] = useState(false);
  const [docsFlyoutOpen, setDocsFlyoutOpen] = useState(false);

  const demoActive = isNavGroupActive(pathname, DEMO_LINKS);
  const docsActive = isNavGroupActive(pathname, DOC_LINKS);

  const closeMobileMenu = () => {
    setMobileOpen(false);
    setDemoOpen(false);
    setDocsOpen(false);
  };

  return (
    <header
      className="sticky top-0 z-[100] border-b border-border backdrop-blur-[14px]"
      style={{ background: "var(--nav-bg)" }}
    >
      <nav className="mx-auto flex min-h-[60px] max-w-[1100px] items-center justify-between gap-4 px-3 py-2">
        <NavBrand />

        <ul className="m-0 hidden list-none flex-1 flex-row flex-wrap items-center justify-center gap-6 p-0 md:flex lg:gap-8">
          <NavLinks links={[ABOUT_LINK]} pathname={pathname} />
          <NavDropdown
            label="Demo"
            links={DEMO_LINKS}
            isActive={demoActive}
            flyoutOpen={demoFlyoutOpen}
            onFlyoutOpenChange={setDemoFlyoutOpen}
            menuId="demo-menu"
            align="left"
          />
          <NavLinks links={[CONTRIBUTORS_LINK]} pathname={pathname} />
          <NavDropdown
            label="Docs"
            links={DOC_LINKS}
            isActive={docsActive}
            flyoutOpen={docsFlyoutOpen}
            onFlyoutOpenChange={setDocsFlyoutOpen}
            menuId="docs-menu"
            align="right"
          />
        </ul>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <GitHubNavLink />
          <ThemeToggle />
          <button
            type="button"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileOpen((o) => !o)}
            className="cursor-pointer rounded-md border border-border bg-transparent px-3 py-2 text-lg leading-none text-foreground hover:text-blue md:hidden"
          >
            {mobileOpen ? "✕" : "☰"}
          </button>
        </div>
      </nav>

      {mobileOpen ? (
        <div className="flex flex-col items-center gap-4 border-t border-border p-4 md:hidden">
          <ul className="m-0 flex w-full list-none flex-col items-center gap-4 p-0">
            <NavLinks
              links={[ABOUT_LINK]}
              pathname={pathname}
              centerOnMobile
              onNavigate={closeMobileMenu}
            />
            <MobileNavSection
              label="Demo"
              links={DEMO_LINKS}
              isActive={demoActive}
              open={demoOpen}
              onOpenChange={setDemoOpen}
              menuId="demo-menu-mobile"
              onNavigate={closeMobileMenu}
            />
            <NavLinks
              links={[CONTRIBUTORS_LINK]}
              pathname={pathname}
              centerOnMobile
              onNavigate={closeMobileMenu}
            />
            <MobileNavSection
              label="Docs"
              links={DOC_LINKS}
              isActive={docsActive}
              open={docsOpen}
              onOpenChange={setDocsOpen}
              menuId="docs-menu-mobile"
              onNavigate={closeMobileMenu}
            />
          </ul>
        </div>
      ) : null}
    </header>
  );
}
