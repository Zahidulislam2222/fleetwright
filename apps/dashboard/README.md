# Dashboard

Next.js/React public website and operator console (Next.js 16.4.6 in the current release). The
production release is a static export behind the same-origin API/update proxy. The console uses
live authenticated data when available, including guest access to the public workspace; offline
mode is labelled reference data and retains local interactions only.

Current release: `20261125-assistant-rc5` (source `26ebe46`), recorded in the
[25 November 2026 release record](../../docs/releases/2026-11-25.md).

| Route | Behavior |
|---|---|
| `/` | Product, architecture and verification overview |
| `/login` | Password/TOTP; restricted shared workspace login |
| `/console/*` | Overview, workers/accounts/claims, filters/schedules, latency, audit and settings; help assistant in the header |
| `/console/workflows` | Exact-action owner review, job investigation, cancellation and evidence download |
| `/board` | Local freight interaction view; the browser worker uses the separately running owned freight exchange |
| `/console/crawl-jobs` | Durable catalogue cycles, quality alerts and operator JSONL exports |
| `/agent` | Setup and launch links for the separate local SQLite/Ollama browser app |

## Run and verify

Run `npm ci` and `npm run dev` from this directory. Generate route types with `npx next typegen`
before a standalone type check. Verify with `npm run lint`, `npm run typecheck`,
`npm run build` and `npm run check:contrast`. Contrast checks cover configured color pairs and do
not establish full accessibility conformance. Read the installed Next.js guides before framework
changes, as required by [AGENTS.md](AGENTS.md).

Maintained display text lives in `src/content/*.json` (assistant labels under `assistant` in
`console.json`). Existing internal file/role names are compatibility identifiers. Security headers
come from `deploy/security-headers.json`; limits and host settings come from deployment
configuration. Build an immutable committed release from the repository root using
`node deploy/build-release.mjs <YYYYMMDD-name>`.

See [product](../../docs/product.md), [console guide](../../docs/console-guide.md),
[deployment](../../docs/operations/deployment.md), [maintenance/accessibility](../../docs/maintenance.md),
[design](../../DESIGN.md) and [security controls](../../docs/security/controls.md).

## Help assistant drawer

`src/components/console/AssistantPanel.tsx` adds a help button to the console header that opens a
side drawer backed by the coordinator's `/v1/assistant` endpoints.

- **Disclosure and marking.** The drawer states that it is an AI before the first question. Each
  answer carries `data-ai-generated="true"` (AI answer) or `"false"` (documentation-search result)
  and an accessible label saying which it is. Answers render as plain text, never HTML; sources and
  the maintained human contact route are shown separately.
- **Accessibility.** The drawer is a labelled modal dialog. Escape closes it and returns focus to
  the help button; progress and results are announced through a polite live region; Send becomes
  Stop while a question is pending, and keyboard focus returns to the question field afterwards.
  "New conversation" discards the current one. The typing indicator respects reduced motion.
- **Layout.** The drawer is rendered through a portal to `<body>`, full height and opaque, and
  covers a 375 px phone screen without horizontal scrolling. A real-browser regression test
  (`apps/coordinator/tests/test_assistant_browser.py`) checks height, opacity and placement after a
  layout defect reached production in this release; see the [defect log](../../DEFECT-LOG.md).
- **Privacy and failure.** The conversation lives only in page memory. Votes go to
  `/v1/assistant/feedback`. The rest of the console stays usable when the assistant is off or failing.

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
complete crawler download, SPA navigation, desktop/mobile checks and a live assistant question.
Observe script-policy errors and hydration on every public route. Pair the static manifest with the
exact native web image; verify the backend independently. See
[release ownership](../../docs/operations/service-ownership.md) and
[scale validation](../../docs/scaling/validation-plan.md).
