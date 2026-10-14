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
| `/console/crawl-jobs` | Durable catalogue cycles, quality alerts and operator JSONL exports |
| `/agent` | Setup and launch links for the separate local SQLite/Ollama browser app |

Run `npm ci` and `npm run dev` from this directory. Generate route types with `npx next typegen`
before a standalone type check. Verify with `npm run lint`, `npm run typecheck`,
`npm run build` and `npm run check:contrast`. Contrast checks cover configured color pairs and do
not establish full accessibility conformance. Read the installed Next.js guides before framework
changes, as required by [AGENTS.md](AGENTS.md).

Maintained display text lives in `src/content/*.json`. Existing internal file/role names are
compatibility identifiers. Security headers come from `deploy/security-headers.json`; limits and
host settings come from deployment configuration. Build an immutable committed release from the
repository root using `node deploy/build-release.mjs <YYYYMMDD-name>`.

See [product](../../docs/product.md), [deployment](../../docs/operations/deployment.md),
[maintenance/accessibility](../../docs/maintenance.md) and [security controls](../../docs/security/controls.md).

## Authorization and release validation

Owner workflow approval and grant issuance require private authenticated authority. Crawler
start/cancel/export require operator-or-owner access; public views expose aggregate state without
those controls. Native UI verification checks real login/TOTP, API responses, exact evidence
exports, SPA navigation, desktop/mobile overflow and browser CSP violations.

The hosted `/agent` route is a launch/setup guide. Its local app connection is explicit; deploying
the dashboard does not install a model or obtain access to the user's browser. Maintain copy in the
content files, preserve established wire identifiers and distinguish runtime data from offline
reference views. Final edge-image scans and exact static-file hashes are separate release gates.

## Public presentation and release evidence

Use professional product language in maintained content values. Preserve established role and
API identifiers when revising labels, and use the publication-copy regression to keep internal
names out of visible presentation. Describe future capacity through the architecture/roadmap;
show measured operational state with its actual observation window.

A dashboard release requires native owner/TOTP/approval interaction, public mutation denial,
complete crawler download, SPA navigation and desktop/mobile checks. Observe script-policy errors
and hydration on every public route. Pair the static manifest with the exact native web image;
verify the backend independently. See [release ownership](../../docs/operations/service-ownership.md)
and [scale validation](../../docs/scaling/validation-plan.md).
