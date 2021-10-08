export const GITHUB_REPO = "https://github.com/chatvector-ai/chatvector-ai";

export const ABOUT_LINK = { label: "About", href: "/about" } as const;

export const DEMO_LINKS = [
  { label: "Chat", href: "/chat" },
  { label: "Batch", href: "/batch" },
  { label: "Status", href: "/status" },
] as const;

export const CONTRIBUTORS_LINK = {
  label: "Contributors",
  href: "/contributors",
} as const;

export const DOC_LINKS = [
  { label: "Getting Started", href: "/getting-started" },
  { label: "Architecture", href: "/architecture" },
  { label: "SDK", href: "/sdk" },
  { label: "Roadmap", href: "/roadmap" },
  { label: "Contributing", href: "/contributing" },
] as const;

export type NavLink = { label: string; href: string };

export function isNavGroupActive(
  pathname: string | null,
  links: ReadonlyArray<{ href: string }>,
): boolean {
  if (!pathname) return false;
  return links.some((link) => pathname.startsWith(link.href));
}
