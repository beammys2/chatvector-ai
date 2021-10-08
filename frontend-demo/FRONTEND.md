# ChatVector frontend design system

This document describes how the marketing homepage, demo app, and navigation are styled so future changes stay consistent with the existing look.

## Color palette

Semantic tokens live in `app/globals.css`. Dark theme defaults are on `:root`; light theme overrides use `[data-theme="light"]`.

### Dark theme (default)

| Token | Value | Role |
| --- | --- | --- |
| `--background` | `#0d1210` | Page backdrop; soft charcoal with a subtle green undertone. |
| `--surface` | `#121816` | Elevated panels: cards, code blocks, inset regions. |
| `--border` | `#202a26` | Hairlines, outlines, grid lines, and dividers. |
| `--foreground` | `#e7ebe8` | Primary text and high-contrast UI chrome. |
| `--muted` | `#a1aaa5` | Secondary copy, captions, de-emphasized labels. |
| `--subtle` | `#46514c` | Tertiary text between border and muted. |
| `--accent` | `#D0A15B` | Warm gold — CTAs, active processing, nav underline, decorative emphasis. |
| `--accent-text` | `#D0A15B` | Gold used specifically as foreground text (kickers, labels). |
| `--accent-foreground` | `#0d1210` | Text/icons on filled gold buttons. |
| `--blue` | `#4f91d9` | Restrained secondary accent; gradients and tags. |
| `--success` / `--success-text` | `#659b7a` / `#7aad8f` | Completed states (upload pipeline, status). |
| `--info` | `#4f7fae` | Neutral/system objects (document icons). |
| `--danger` / `--danger-text` | `#c75b5b` / `#d97070` | Failure and error states. |
| `--code-bg` | `#101513` | Code block body (theme-invariant dark surface). |
| `--nav-bg` | `rgba(13, 18, 16, 0.9)` | Sticky nav scrim. |

### Light theme

Warm off-white counterpart: `--background` `#f6f5f1`, `--surface` `#fbfaf7`, `--foreground` `#171b19`, `--accent-text` `#A97830` (darker gold for small text contrast), `--blue` / `--info` `#4f7fae`, matching `--success` / `--danger` family. `--accent` stays `#D0A15B` for fills and borders.

Headline gradients use `--headline-gradient`: gold → slate-blue → muted blue in light mode; gold → blue in dark mode. Apply via the `.text-headline-gradient` utility.

**Non-token colors:** IDE syntax highlighting hues, macOS window dots, and per-feature card icon colors remain intentional exceptions.

## Font stack

- **DM Sans** — body copy, headings, and UI text (`--font-sans`, applied on `body`).
- **JetBrains Mono** — kickers, code windows, tags, logo (`--font-mono`).

`app/layout.tsx` may still load Geist via `next/font`; it is unused by `@theme` and can be removed to avoid extra font downloads.

## Spacing and layout conventions

- **Content width:** Main column `max-w-[1100px]` with `px-8` on sections; nav uses `max-w-[1100px]` and `px-4`.
- **Vertical rhythm:** Major sections `py-24`. Hero uses `pt-20` / `pb-16` / `px-8`.
- **Grids:** Two-column blocks `gap-12` and `md:grid-cols-2`. Feature cards `grid-cols-[repeat(auto-fit,minmax(240px,1fr))]` with `gap-6`.
- **Cards:** `rounded-xl`, `border border-border`, consistent inner padding.

## Component patterns

- **Section header:** `Kicker` component (`// label`) in `font-mono`, uppercase, `text-accent-text`; title in `text-foreground`; supporting copy `text-muted`.
- **Primary CTA:** Filled `bg-accent`, `text-accent-foreground`, `rounded-lg`, hover lift.
- **Secondary CTA:** `border border-border`, transparent background, `hover:border-subtle`, `hover:bg-surface`.
- **Active nav:** Foreground label color plus gold underline via `.nav-link-active::after` (not gold text).
- **User chat bubble:** `.chat-bubble-user` — subtle gold tint and border, `foreground` text (not solid gold fill).
- **Assistant chat bubble:** Neutral `bg-surface`.
- **Upload pipeline:** Gold = active step; green (`success`) = completed; red (`danger`) = failed; muted = pending.
- **Code window:** `bg-code-bg` body, title bar `bg-surface`, traffic-light dots, filename in `font-mono` + `text-muted`.
- **Feature card:** Section on `bg-surface`; cards on `bg-background`, hover `border-subtle` and slight lift. Tag pills use `color-mix` with `var(--blue)`.

## Tailwind vs inline styles

**Default rule:** Prefer Tailwind utilities. Tokens are registered in `globals.css` inside `@theme inline` as `--color-*`, producing utilities like `bg-surface`, `text-accent-text`, `text-success`, `border-border`.

**`tailwind.config.ts`:** Mirrors `theme.extend.colors` for editor tooling; Tailwind v4 primarily reads `@theme` from CSS.

**When inline styles are OK:** Radial/repeating gradients, exact `color-mix` alpha values, and fully dynamic syntax-highlight or feature-icon colors. Do not introduce new hardcoded hex for semantic UI — use tokens.
