# Fleetwright design usage

This file explains how to use the design system. It does not repeat values: every colour, spacing,
radius, motion and layer value is defined once in the token source below (global Rule 25).

## Where the values live

| What | Source of truth |
|---|---|
| Landing tokens (scene colours, motion, gutters, radii, z-layers) | `:root` in [`apps/dashboard/src/app/globals.css`](apps/dashboard/src/app/globals.css) |
| Console tokens (`--c-*`, light and dark via `light-dark()`) | `.console-theme` in the same file |
| Motion presets | [`apps/dashboard/src/design/motion.ts`](apps/dashboard/src/design/motion.ts) |
| Console copy, labels and assistant text | [`apps/dashboard/src/content/console.json`](apps/dashboard/src/content/console.json) |
| Original brief, screens and acceptance | [`design/PHASE1-FRONTEND-SPEC.md`](design/PHASE1-FRONTEND-SPEC.md) |
| Owned freight exchange styling (separate, deliberately plain destination; package `apps/mockboard`) | [`apps/mockboard/src/mockboard/static/board.css`](apps/mockboard/src/mockboard/static/board.css) |

## Rules of use

- Console UI uses only `--c-*` tokens through Tailwind classes such as `bg-c-surface`, `text-c-text-2`,
  `border-c-border`. Never write a raw colour in a component.
- Text on surfaces uses `--c-text`, `--c-text-2` or `--c-text-3`; status uses the `--c-ok`, `--c-warn`,
  `--c-bad`, `--c-info` pairs with their `*-bg` backgrounds. Accent (`--c-accent`) is for one primary
  action or focus, with `--c-on-accent` text.
- Form controls use `--c-input-border` (≥ 3:1 non-text contrast). Run `npm run check:contrast` after any
  token change; both themes must pass WCAG 2.2 AA.
- Layers use the `--z-*` scale (sticky header, overlay for drawers and the assistant panel, toast).
- Every data view has loading, empty, error and permission-denied states (see `ui.tsx`); new panels
  reuse them, including an "AI unavailable" state for the assistant.
- Respect `prefers-reduced-motion` (`usePrefersReducedMotion`); motion never carries meaning alone.
- Dialogs and drawers use `useDialog` (focus trap, Escape, focus return). Icons come from `lucide-react`
  with `aria-hidden` and a visible or screen-reader label.

## Components to reuse before adding new ones

`ConsoleShell` (header, navigation, drawer), `ui.tsx` (cards, states, badges), `DataTable`, `Toolbar`,
`RadioGroup`, `charts.tsx`. The console help assistant (`AssistantPanel`) follows the drawer pattern.
