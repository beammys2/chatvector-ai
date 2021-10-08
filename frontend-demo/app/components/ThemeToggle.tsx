"use client";

import { useEffect } from "react";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle() {
  // Sync with OS-level preference changes when no manual choice is stored
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const handleChange = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem("theme")) {
        document.documentElement.setAttribute(
          "data-theme",
          e.matches ? "light" : "dark"
        );
      }
    };
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const toggle = () => {
    const current =
      document.documentElement.getAttribute("data-theme") ?? "dark";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle theme"
      className="cursor-pointer rounded-md border border-border bg-transparent p-2 text-foreground transition-colors duration-200 hover:border-accent hover:bg-accent/10 hover:text-accent-text"
    >
      {/* CSS-driven — no React state, no hydration mismatch, no flash */}
      <Sun
        className="size-[1.1rem] hidden [[data-theme=light]_&]:block"
        aria-hidden
      />
      <Moon
        className="size-[1.1rem] [[data-theme=light]_&]:hidden"
        aria-hidden
      />
    </button>
  );
}
