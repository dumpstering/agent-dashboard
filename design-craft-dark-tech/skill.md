---
name: dark-tech
description: Dark-first interfaces inspired by Vercel, Linear, and Raycast. Monospace data, geometric sans UI, borders over shadows, keyboard-first, command palette patterns. For developer tools, technical products, and precision-obsessed dark UIs.
---

# Dark Tech

The IDE at 2am. A deploy log scrolling in the sidebar. The command palette answering before you finish typing. Software for people who think in keyboard shortcuts and read changelogs for fun. Every pixel is information. Nothing decorates.

---

## Color System

Dark-first. Slate/zinc base. One accent, used surgically. CSS custom properties in OKLCH.

```css
:root {
  --dt-bg-root: oklch(0.13 0.02 265);        /* app background */
  --dt-bg-surface: oklch(0.16 0.02 265);      /* cards, panels */
  --dt-bg-elevated: oklch(0.19 0.02 265);     /* popovers, dropdowns */
  --dt-bg-overlay: oklch(0.13 0.02 265 / 80%);/* modal backdrop */
  --dt-bg-subtle: oklch(0.22 0.01 265);       /* hover, active rows */
  --dt-border: oklch(1 0 0 / 10%);            /* default separator */
  --dt-border-strong: oklch(1 0 0 / 15%);     /* emphasized edges */
  --dt-border-subtle: oklch(1 0 0 / 6%);      /* faint grid lines */
  --dt-text-primary: oklch(0.95 0.01 265);    /* headlines, values */
  --dt-text-secondary: oklch(0.65 0.02 265);  /* body, descriptions */
  --dt-text-muted: oklch(0.45 0.02 265);      /* labels, timestamps */
  --dt-text-faint: oklch(0.35 0.01 265);      /* disabled, placeholder */
  --dt-accent: oklch(0.65 0.15 250);          /* single accent (blue) */
  --dt-accent-muted: oklch(0.65 0.15 250 / 15%);
  --dt-accent-text: oklch(0.78 0.12 250);
  --dt-success: oklch(0.65 0.15 155);
  --dt-warning: oklch(0.72 0.12 80);
  --dt-error: oklch(0.62 0.2 25);
}
```

**Rules:** Never pure black (`#000`) -- always tinted dark. Never pure white text -- `oklch(0.95)` max. Accent appears only on interactive elements, active states, and focus rings. Status colors desaturated 15-20% vs light-mode equivalents. Build hierarchy through lightness and opacity, not hue.

---

## Typography

Two tracks: monospace for data, geometric sans for UI.

```css
:root {
  --dt-font-mono: "Geist Mono", "JetBrains Mono", "SF Mono", ui-monospace, monospace;
  --dt-font-sans: "Geist", "Inter", -apple-system, system-ui, sans-serif;
}
```

**Mono for:** numbers, prices, IDs, hashes, timestamps, code, keyboard shortcuts, version numbers, status badges.
**Sans for:** navigation, labels, buttons, page titles, headers, body text, descriptions.

### Type Scale (Tight)

Base is 13px, not 16px. Developer tools reward density.

| Token | Size | Use |
|-------|------|-----|
| `--dt-text-xs` | 11px | Labels, metadata |
| `--dt-text-sm` | 12px | Secondary content |
| `--dt-text-base` | 13px | Default body |
| `--dt-text-md` | 14px | Emphasis |
| `--dt-text-lg` | 16px | Section headers |
| `--dt-text-xl` | 20px | Page titles |
| `--dt-text-2xl` | 24px | Hero numbers |

**Non-negotiable:** `font-variant-numeric: tabular-nums lining-nums` on every data column. Numbers must align vertically.

---

## Depth: Borders Over Shadows

On dark backgrounds, shadows are nearly invisible and add noise. Borders at low white opacity create clean separation.

- **Default separator:** `1px solid var(--dt-border)` (10% white)
- **Emphasized edge:** `1px solid var(--dt-border-strong)` (15% white)
- **Faint division:** `1px solid var(--dt-border-subtle)` (6% white)

Shadows allowed ONLY on floating layers (dropdowns, command palette, tooltips):
```css
--dt-shadow-float: 0 8px 30px oklch(0 0 0 / 40%), 0 0 0 1px var(--dt-border);
```

Always include a 1px border even on shadowed elements. Border provides the crisp edge; shadow provides the depth.

**Elevation = lighter background, not shadow.** Root `0.13L` < Surface `0.16L` < Elevated `0.19L`.

---

## Motion

Fast, crisp, no bounce. Developer tools feel instant.

| Token | Duration | Use |
|-------|----------|-----|
| `--dt-duration-instant` | 80ms | Focus rings, active states |
| `--dt-duration-fast` | 120ms | Hover, toggle, tab switch |
| `--dt-duration-normal` | 150ms | Panels, expand/collapse |
| `--dt-duration-slow` | 200ms | Modals, page transitions |

Easing: `cubic-bezier(0.25, 1, 0.5, 1)` -- quick start, gentle stop.

**Rules:** Hover = color change only, no scale/translate. Never animate box-shadow -- change border-color instead. No loading spinners -- use skeleton shimmer (`background-position` animation). `prefers-reduced-motion: reduce` disables ALL transitions, no exceptions.

---

## Component Patterns

### Command Palette (cmdk-style)

`Cmd+K` opens everything. The signature dark-tech interaction.

- Full-width input at top, no visible border, large monospace font
- Group labels: `--dt-text-muted`, uppercase, 11px, `letter-spacing: 0.05em`
- Items: primary text left, keyboard shortcut right-aligned in mono
- Active item: `--dt-bg-subtle` background with accent left border
- Backdrop: `--dt-bg-overlay` with `backdrop-filter: blur(8px)`
- Opens/closes in 150ms, no bounce

### Data Tables

Dense, scannable, keyboard-navigable. Row height 32-36px.

- Headers: sans, 500 weight, 11px, uppercase, `letter-spacing: 0.04em`, `--dt-text-muted`, sticky
- Cells: 12px, `--dt-text-secondary`, numeric columns in mono with `tabular-nums`
- Row separator: `--dt-border-subtle`. No alternating row colors.
- Hover: `--dt-bg-subtle` highlight on entire row
- Selected row: `--dt-accent-muted` background

### Stat Cards

Numbers as heroes. Labels as footnotes.

- Value: mono, 24px, 600 weight, `--dt-text-primary`
- Label: sans, 11px, uppercase, `letter-spacing: 0.04em`, `--dt-text-muted`
- Trend indicator: small inline arrow + percentage in `--dt-success`/`--dt-error`, mono
- Surface: `--dt-bg-surface` with `--dt-border`, no shadow

### Changelog / Activity Feed

- Version numbers: mono, `--dt-text-primary`, bold
- Timestamps: mono, `--dt-text-muted`, right-aligned
- Descriptions: sans, `--dt-text-secondary`
- "Breaking" labels: `--dt-error` color
- Entries separated by `--dt-border-subtle`, not whitespace gaps

### Keyboard Shortcut Display

```css
.dt-kbd {
  font-family: var(--dt-font-mono);
  font-size: 11px;
  padding: 2px 6px;
  border: 1px solid var(--dt-border-strong);
  border-radius: 4px;
  background: var(--dt-bg-elevated);
  color: var(--dt-text-muted);
}
```

---

## Code and Terminal Aesthetics

Code blocks and terminal output are first-class content.

### Code Blocks

- Font: `--dt-font-mono`, 12px, `line-height: 1.6`, `tab-size: 2`
- Background: `--dt-bg-root` (darkest), `1px solid var(--dt-border)`, `border-radius: 6px`
- Language badge: top-right, `--dt-text-muted`, 11px
- Copy button: top-right, appears on hover, icon only
- Syntax colors: muted palette. Comments `--dt-text-faint`. Strings desaturated green. Keywords in accent color. No neon glow.

### Terminal Windows

- Header: `--dt-bg-surface`, three dots in `--dt-text-faint` (not traffic-light colored), title centered in `--dt-text-muted`
- Body: `--dt-bg-root`, `--dt-text-secondary`, prompt prefix in `--dt-text-muted`
- Window chrome should be invisible, not decorative

---

## Information Density and Keyboard-First

### Spacing Scale (4px grid)

`4px` icon gaps | `8px` within components | `12px` related items | `16px` component padding | `24px` between sections | `32px` major page divisions

### Keyboard-First Requirements

- All interactive elements reachable by `Tab`
- Focus rings: `outline: 2px solid var(--dt-accent); outline-offset: 2px;`
- Arrow keys navigate within components (tables, lists, tabs)
- `Escape` closes any overlay
- Shortcut hints visible in menus and tooltips

### Sidebar Navigation

Same background as content area. Border separates, not color (Linear/Vercel pattern).

- Nav items: 12px sans, `--dt-text-secondary`, 6px vertical padding
- Hover: `--dt-bg-subtle` background
- Active: `--dt-accent-muted` background, `--dt-accent-text` color
- Group labels: 11px, uppercase, `--dt-text-muted`

---

## Mobile Adaptations

Maintain density. Do NOT add generous padding to "make it mobile friendly."

- **Tables:** horizontally scrollable with pinned first column, not card stacks. Add right-edge fade gradient as scroll hint.
- **Command palette:** full-screen bottom sheet, not centered modal
- **Sidebar:** collapses to hamburger, slides in as overlay
- **Stat cards:** 2-column grid minimum, never single-column stack
- **Touch targets:** 44px minimum height via padding, not font-size increase
- **Code blocks:** full-width with horizontal scroll, 12px font minimum

---

## Anti-Convergence: Bans and Requirements

### Banned

- Border-radius > 8px (no pill buttons, no 16px+ radius)
- Drop shadows on cards
- Gradient backgrounds on surfaces
- Colored section backgrounds (light purple for "features", light blue for "pricing")
- Spring/bounce animations
- Loading spinners
- Decorative illustrations or mascots
- Emojis as UI elements
- Multiple accent colors
- Box shadows for hover states
- Thick borders (> 1px) for structural elements
- White/light card surfaces on dark backgrounds
- Neon glow effects on text or borders

### Required

- `tabular-nums` on every number column
- Visible keyboard shortcuts in menus
- `prefers-reduced-motion` respected
- Monospace for all data values
- Border-radius max: 4px (small), 6px (cards), 8px (modals)
- Semantic HTML with `aria-*` attributes
- Focus-visible outlines on all interactives

---

## Reference Sites

| Site | Study For |
|------|-----------|
| **vercel.com** | Surface hierarchy, stat cards, deploy logs, dark depth |
| **linear.app** | Command palette, keyboard-first nav, issue density |
| **raycast.com** | Extension marketplace, shortcut display, speed feel |
| **resend.com** | Email logs as data tables, monospace data, minimal accent |
| **supabase.com** | Sidebar nav, SQL editor integration, code-first dashboard |

---

## Tailwind v4 Integration

```css
@import "tailwindcss";
@custom-variant dark (&:where(.dark, .dark *));

@theme {
  --font-mono: "Geist Mono", "JetBrains Mono", ui-monospace, monospace;
  --font-sans: "Geist", "Inter", system-ui, sans-serif;
  --color-dt-bg: oklch(0.13 0.02 265);
  --color-dt-surface: oklch(0.16 0.02 265);
  --color-dt-elevated: oklch(0.19 0.02 265);
  --color-dt-border: oklch(1 0 0 / 10%);
  --color-dt-text: oklch(0.95 0.01 265);
  --color-dt-muted: oklch(0.45 0.02 265);
  --color-dt-accent: oklch(0.65 0.15 250);
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --ease-snappy: cubic-bezier(0.25, 1, 0.5, 1);
}
```

Apply `class="dark"` on `<html>`. This is dark-first -- light mode is the afterthought.
