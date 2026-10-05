# Phase 1 — Frontend design spec (landing + clickable console prototype)

Written 2026-10-05, before implementation (gate workflow phase 1). Source of the workflow: the user's
video instructions — Motion for React, the UI UX Pro Max skill, a MotionSites prompt as visual reference.

## 1. Brief

| Decision | Value |
|---|---|
| Audience | Freelance-platform clients evaluating a bid (Post 1 crawling, Post 2 distributed Playwright claiming, Post 3 local AI agent); technical buyers |
| Primary task | Understand in under a minute what Fleetwright guarantees (one claim per job, auditable latency, crash-safe), then open the console prototype |
| Subject | A fleet of browser workers coordinated by one control plane; claims; cells; latency stages |
| Promise and proof | Promise = design guarantees from BUILD_PLAN. Proof today = the clickable console on mock data. Measured numbers do not exist yet and must not be shown as measured |
| Creative proposition | A fleet at night converging on one beacon: many vessels, exactly one lands. The motion explains the claim guarantee |
| Constraints | No fake customers, logos or metrics. No real third-party target. WCAG 2.2 AA. Smooth scroll. Paid media within the OpenRouter key cap |

## 2. Reference record

```
URL / creator / date: https://motionsites.ai/?prompt=ai-runtime  ("AI Runtime", design by Ritu), inspected 2026-10-05
Viewed: live gallery thumbnail + full copied prompt (scratch copy, not committed)
Principle adopted: single full-bleed video viewport; white nav pill + dark sign-in pill; dot-matrix
  display headline in two solid-white lines; muted subhead; one glowing white CTA; 4-stat footer with
  count-up; staggered blur-rise entrance (0.85s, cubic-bezier(0.22,1,0.36,1)); mobile burger sheet.
Deliberately NOT adopted:
  - hot-linked third-party CloudFront video (no licence) -> own Seedance 2.5 video
  - "Trusted by 2000+ Enterprises" + Microsoft/Amazon/Google marks (fabricated proof, trademark risk)
    -> honest "worker types" ring row + "design prototype, mock data" pill
  - invented stats (120ms, 99.99%, 2.4M) -> BUILD_PLAN design targets, labelled as targets
  - BubbledotICG font from an unlicensed CDN -> Geist Pixel Circle (OFL, npm `geist`)
  - single viewport only -> the hero is viewport one of a smooth-scrolled story
```

## 3. Design system (UI UX Pro Max output, synthesised)

Queries run: `"B2B developer tool SaaS landing" --design-system` (pattern Hero + Features + CTA) and
`"operations monitoring dashboard realtime" --design-system --density 8` (Real-Time / Operations
pattern; status green/amber/red; live labels only with a real source + update time + pause control).
Its generic blue/orange palette was rejected in favour of the reference's black + white, with one
signal accent (beacon amber) and functional status colours. Tokens live in `apps/dashboard/src/app/globals.css`.

## 4. Landing page beats (`/`)

1. Hero — video fleet background, nav, worker-type rings, headline, subhead, CTA, 4 target stats.
2. Problem — scroll-linked word reveal: fifty workers, one load, twelve clicks.
3. Claim race — pinned, scroll-scrubbed three.js scene: workers converge, Postgres unique key picks one
   winner, the rest are rejected; a stale lease is fenced out. State-machine labels in DOM.
4. Three worker types — stacking cards (Crawler / Claimer / Agent) with real UI fragments.
5. Latency trace — six instrumented timestamps, pinned horizontal track on desktop, list on mobile.
6. Cells — interactive "fail cell A" toggle; cell B keeps claiming.
7. Guardrails — security + law commitments.
8. Closing CTA + honest footer.

## 5. Console prototype (`/console/*`, `/login`, `/agent`, `/board`)

Screens from BUILD_PLAN Phase 1: login + MFA; fleet overview; workers; accounts & sessions; filters;
schedules; claims timeline; latency; crawl jobs; audit log; settings; agent window (task chat, step
log, approval queue); mock load board (login, OTP, jobs feed, booking, captcha). Every data screen
supports ready / loading / empty / error / permission-denied via a prototype state switcher. Data is
typed mock data with `tenant_id` and cursor fields, clearly labelled "mock data".

## 6. Acceptance criteria

| # | Criterion | How verified |
|---|---|---|
| A1 | Hero reproduces the reference composition (nav pill, rings row, 2-line dot-matrix headline, subhead, glowing CTA, 4 stats with count-up) at 1440 and 390 widths | Screenshots at both widths |
| A2 | No fabricated customers, logos or measured-looking metrics; every number is labelled a design target or mock | Text review of rendered page |
| A3 | Smooth scroll (Lenis) on wheel; native scroll on touch; anchors and keyboard scrolling still work | Browser test: wheel, anchor click, Space/PageDown |
| A4 | `prefers-reduced-motion` shows final states: no smooth-scroll inertia, no scrubbed 3D, video paused to poster | Emulated reduced motion |
| A5 | Claim-race section is scroll-scrubbed both directions and its explanation is readable in DOM without WebGL | Scroll up/down; WebGL disabled path |
| A6 | Hero video is our own generated asset with a poster; page is fully usable if video fails | Network block of video |
| A7 | All console screens listed in §5 exist and are reachable from navigation | Click-through |
| A8 | Each console data screen renders ready / loading / empty / error / denied states | State switcher click-through |
| A9 | Console has light and dark themes; token text pairs pass WCAG AA (4.5:1 body, 3:1 large/UI) | `npm run check:contrast` |
| A10 | Keyboard: visible focus everywhere, skip link, mobile menu closes on Escape | Keyboard walk-through |
| A11 | No horizontal scroll at 375px; layouts hold at 375 / 768 / 1024 / 1440 | Screenshots + scrollWidth check |
| A12 | Content copy, stats, nav and media paths come from data files, not component literals (Rule 12) | Code review + grep |
| A13 | Gates: eslint clean, `tsc --noEmit` clean, `next build` succeeds, security hook clean | Command output |
| A14 | Paid generation stays inside the key cap; every job's model, settings and reported cost recorded | `design/media/MANIFEST.md` |

Out of scope for this step (still Phase 1 exit items in BUILD_PLAN): `openapi.yaml` + contract test,
Compose skeleton, CI, ADRs, threat model, legal register.
