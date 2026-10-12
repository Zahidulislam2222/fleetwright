# Dashboard

Next.js/React public website and operator console. The production release is a static export
behind the same-origin API/update proxy. The console uses live authenticated data when available;
offline mode is labelled reference data and retains local interactions only.

| Route | Behavior |
|---|---|
| `/` | Product, architecture and verification overview |
| `/login` | Password/TOTP; restricted shared workspace login |
| `/console/*` | Overview, workers/accounts/claims, filters/schedules, latency, audit and settings |
| `/console/workflows` | Exact-action owner review, job investigation, cancellation and evidence download |
| `/board` | Local freight interaction view; the browser worker uses the separately running destination |
| `/agent` | Planned standalone interface with local interaction data; real execution uses MCP |

Run `npm ci` and `npm run dev` from this directory. Verify with `npm run lint`, `npm run typecheck`,
`npm run build` and `npm run check:contrast`. Contrast checks cover configured color pairs and do
not establish full accessibility conformance. Read the installed Next.js guides before framework
changes, as required by [AGENTS.md](AGENTS.md).

Maintained display text lives in `src/content/*.json`. Existing internal file/role names are
compatibility identifiers. Security headers come from `deploy/security-headers.json`; limits and
host settings come from deployment configuration. Build an immutable committed release from the
repository root using `node deploy/build-release.mjs <YYYYMMDD-name>`.

See [product](../../docs/product.md), [deployment](../../docs/operations/deployment.md),
[maintenance/accessibility](../../docs/maintenance.md) and [security controls](../../docs/security/controls.md).
