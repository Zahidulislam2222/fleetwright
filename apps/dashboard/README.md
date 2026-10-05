# Dashboard (`apps/dashboard`)

The public website and the operator console, built with Next.js 16 and React 19 as a **static
export** (served by a plain web server or a CDN).

Live: <https://fleetwright.zahidul-islam.com>

## Routes

| Route | What it is |
|---|---|
| `/` | Landing page |
| `/console/*` | Operator console: overview, workers, accounts, claims, filters, schedules, latency, crawl jobs, audit log, settings |
| `/login` | Sign-in with password and one-time code (design) |
| `/board` | Preview of the mock load board |
| `/agent` | Preview of the local AI agent window |

## Status

The console is a **design prototype on mock data** (`src/mocks/`). Every screen has ready,
loading, empty, error and permission-denied states, and light and dark themes. The data shapes in
`src/mocks/types.ts` are the contract the real API implements; wiring the console to the live
engine is in progress ([roadmap](../../docs/roadmap.md)). The mocks will stay as a contract-test
fixture.

## Develop

```bash
npm ci
npm run dev          # http://localhost:3000
npm run lint
npm run typecheck
npm run build        # production build
npm run check:contrast   # WCAG contrast of every colour pair
```

Release bundles for the server are built from the repository root with
`node deploy/build-release.mjs <YYYYMMDD-name>` (static export, web server config and a SHA-256
manifest for parity checks).

## Notes for contributors

- This Next.js version has breaking changes compared with older versions; read the guides in
  `node_modules/next/dist/docs/` before changing framework-level code (see `AGENTS.md`).
- Copy lives in `src/content/*.json`, not in components.
- Security headers (Content-Security-Policy and others) are defined in
  `deploy/security-headers.json` and applied by the web server.
